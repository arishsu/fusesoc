import logging
import os.path
import platform
from fusesoc import utils

from fusesoc.edatool import EdaTool

logger = logging.getLogger(__name__)

tool_options = {'members' : {'part' : 'String'}}

""" Vivado Backend

The Vivado backend executes Xilinx Vivado to build systems and program the FPGA.

The backend defines the following section:

    [vivado]
    part = <part name> # Format <family><device><package>-<speedgrade>
    hw_device = <device name> # Format <family><device>_0
    top_module = <RTL module name>

A core (usually the system core) can add the following files:

- Standard design sources

- Constraints: Supply xdc files with file_type=xdc

- IP: Supply the IP core xci file with file_type=xci and other files (like .prj)
      as file_type=data
"""
class Vivado(EdaTool):

    argtypes = ['vlogdefine', 'vlogparam']

    """ Configuration is the first phase of the build

    This writes the project TCL files and Makefile. It first collects all
    sources, IPs and contraints and then writes them to the TCL file along
     with the build steps.
    """
    def configure_main(self):
        (src_files, incdirs) = self._get_fileset_files(force_slash=True)

        self.jinja_env.filters['src_file_filter'] = self.src_file_filter

        has_vhdl2008 = 'vhdlSource-2008' in [x.file_type for x in src_files]

        template_vars = {
            'name'         : self.name,
            'src_files'    : src_files,
            'incdirs'      : incdirs,
            'tool_options' : self.tool_options,
            'toplevel'     : self.toplevel,
            'vlogparam'    : self.vlogparam,
            'vlogdefine'   : self.vlogdefine,
            'has_vhdl2008' : has_vhdl2008,
        }

        self.render_template('vivado-project.tcl.j2',
                             self.name+'.tcl',
                             template_vars)

        self.render_template('vivado-makefile.j2',
                             'Makefile',
                             {'name' : self.name})

        self.render_template('vivado-run.tcl.j2',
                             self.name+"_run.tcl")

        template_vars = {
            'bitstream_name' : self.name+'.bit'
            'hw_device'      : self.tool_options['hw_device'],
        }
        self.render_template('vivado-program.tcl.j2',
                             self.name+"_pgm.tcl",
                             template_vars)

    def render_template(self, template_file, target_file, template_vars = {}):
        template = self.jinja_env.get_template(os.path.join('vivado', template_file))
        file_path = os.path.join(self.work_root, target_file)
        with open(file_path, 'w') as f:
            f.write(template.render(template_vars))

    def src_file_filter(self, f):
        def _vhdl_source(f):
            s = 'read_vhdl'
            if f.file_type == 'vhdlSource-2008':
                s += ' -vhdl2008'
            if f.logical_name:
                s += ' -library '+f.logical_name
            return s

        file_types = {
            'verilogSource'       : 'read_verilog',
            'systemVerilogSource' : 'read_verilog -sv',
            'vhdlSource'          : _vhdl_source(f),
            'xci'                 : 'read_ip',
            'xdc'                 : 'read_xdc',
            'tclSource'           : 'source',
        }
        _file_type = f.file_type.split('-')[0]
        if _file_type in file_types:
            return file_types[_file_type] + ' ' + f.name
        elif _file_type == 'user':
            return ''
        else:
            _s = "{} has unknown file type '{}'"
            logger.warning(_s.format(f.name,
                                     f.file_type))
        return ''

    """ Program the FPGA

    For programming the FPGA a vivado tcl script is written that searches for the
    correct FPGA board and then downloads the bitstream. The tcl script is then
    executed in Vivado's batch mode.
    """
    def run(self, remaining):
        tcl_file_name = self.name+"_pgm.tcl"
        utils.Launcher('vivado', ['-mode', 'batch', '-source', tcl_file_name ],
                       cwd = self.work_root,
                       errormsg = "Failed to program the FPGA").run()
