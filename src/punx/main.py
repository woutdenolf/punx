#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# :author:    Pete R. Jemian
# :email:     prjemian@gmail.com
# :copyright: (c) 2016, Pete R. Jemian
#
# Distributed under the terms of the Creative Commons Attribution 4.0 International Public License.
#
# The full license is in the file LICENSE.txt, distributed with this software.
#-----------------------------------------------------------------------------

'''
Python Utilities for NeXus HDF5 files

main user interface file

.. rubric:: Usage

::

    usage: punx [-h] [-v] {hierarchy,show,structure,update,validate} ...
    
    Python Utilities for NeXus HDF5 files URL: http://punx.readthedocs.io
    v0.0.1+4.gff00892.dirty
    
    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
    
    subcommands:
      valid subcommands
    
      {demo,structure,update,validate}
        demo                validate NeXus  demo file: writer_1_3.hdf5
        hierarchy           TBA: show NeXus base class hierarchy
        show                TBA: show program information (about the cache)
        structure           show structure of HDF5 file
        update              update the local cache of NeXus definitions
        validate            validate a NeXus file

'''

import argparse
import os
import sys

import __init__


# :see: https://docs.python.org/2/library/argparse.html#sub-commands
# obvious 1st implementations are h5structure and update


def func_demo(args):
    '''
    show what **punx** can do
    
    .. index:: demo
    '''
#     print 'punx update '
#     args.force = False
#     func_update(args)

    path = os.path.dirname(__file__)
    args.infile = os.path.abspath(os.path.join(path, 'data', 'writer_1_3.hdf5'))

    print 'console> punx validate ' + args.infile
    func_validate(args)

    print 'console> punx structure ' + args.infile
    import h5structure
    mc = h5structure.h5structure(args.infile)
    #    :param bool show_attributes: display attributes in output
    show_attributes=True
    mc.array_items_shown = 5
    print '\n'.join(mc.report(show_attributes))


def func_hierarchy(args):
    url = 'http://punx.readthedocs.io/en/latest/analyze.html'
    print 'A chart of the NeXus is in the **punx** documentation.'
    print 'see: ' + url


def func_show(args):
    print 'still in development -- not implemented yet'
    print args


def func_structure(args):
    if args.infile.endswith('.nxdl.xml'):
        import nxdlstructure
        nxdl = nxdlstructure.NXDL_definition(args.infile)
        print nxdl.render()
    else:
        import h5structure
        
        #    :param int limit: maximum number of array items to be shown (default = 5)
        limit=5
        #    :param bool show_attributes: display attributes in output
        show_attributes=True
        
        mc = h5structure.h5structure(os.path.abspath(args.infile))
        mc.array_items_shown = limit
        print '\n'.join(mc.report(show_attributes) or '')


def func_update(args):
    import cache
    cache.update_NXDL_Cache(force_update=args.force)


def func_validate(args):
    import validate
    if args.infile.endswith('.nxdl.xml'):
        result = validate.validate_xml(args.infile)
        if result is None:
            print args.infile, ' validates'
    else:
        import finding
        try:
            validator = validate.Data_File_Validator(args.infile)
        except IOError, _exc:
            print 'File not found: ' + args.infile
            exit(1)
        validator.validate()

        # report the findings from the validation
        #  finding.SHOW_ALL        finding.SHOW_NOT_OK        finding.SHOW_ERRORS
        show_these = finding.SHOW_ALL
        print 'Validation findings'
        print ':file: ' + os.path.basename(validator.fname)
        print ':validation results shown: ', ', '.join(sorted(map(str, show_these)))
        print validator.report_findings(show_these)
        
        print 'summary statistics'
        print validator.report_findings_summary()


class MyArgumentParser(argparse.ArgumentParser):
    '''
    override standard ArgumentParser to enable shortcut feature
    
    stretch goal: permit the first two char (or more) of each subcommand to be accepted
    # ?? http://stackoverflow.com/questions/4114996/python-argparse-nargs-or-depending-on-prior-argument?rq=1
    '''
    
    def parse_args(self, args=None, namespace=None):
        '''
        permit the first two char (or more) of each subcommand to be accepted
        '''
        if args is None:
            # args default to the system args
            args = sys.argv[1:]
        if len(args) > 0:
            # make a list of the available subcommand names
            choices = []
            for g in self._subparsers._group_actions:
                if isinstance(g, argparse._SubParsersAction):
                    #choices = g._name_parser_map.keys()
                    choices = g.choices.keys()
                    break
            if len(choices) > 0 and args[0] not in choices:
                if len(args[0]) < 2:
                    msg = 'subcommand too short, must match first 2 or more characters, given: %s'
                    self.error(msg % ' '.join(args))
                # look for any matches
                matches = [c for c in choices if c.startswith(args[0])]
                # validate the match is unique
                if len(matches) == 0:
                    msg = 'subcommand unrecognized, given: %s'
                    self.error(msg % ' '.join(args))
                elif len(matches) > 1:
                    msg = 'subcommand ambiguous (matches: %s)' % ' | '.join(matches)
                    msg += ', given: %s'
                    self.error(msg % ' '.join(args))
                else:
                    args[0] = matches[0]
        # make sure that args are mutable
        args = list(args)
        return argparse.ArgumentParser.parse_args(self, args, namespace)


def parse_command_line_arguments():
    '''process command line'''
    doc = __doc__.strip().splitlines()[0]
    doc += '\n  URL: ' + __init__.__url__
    doc += '\n  v' + __init__.__version__
    p = MyArgumentParser(prog=__init__.__package_name__, 
                                     description=doc,
                                     epilog=__init__.__url__)

    p.add_argument('-v', 
                        '--version', 
                        action='version', 
                        version=__init__.__version__)

    # TODO: stretch goal: GUI for any of this
    # p.add_argument('-g', 
    #                     '--gui', 
    #                     help='graphical user interface (TBA)')

    sub_p = p.add_subparsers(title='sub_p', description='valid sub_p',)
    
    
    ### subcommand: demo
    p_demo = sub_p.add_parser('demo', help='demonstrate HDF5 file validation')
    p_demo.set_defaults(func=func_demo)


    ### subcommand: hierarchy
    p_hierarchy = sub_p.add_parser('hierarchy',  help='show NeXus base class hierarchy')
    p_hierarchy.set_defaults(func=func_hierarchy)
    #p_hierarchy.add_argument('something', type=bool, help='something help')


    ### subcommand: show
#     p_show = sub_p.add_parser('show', help='show program information (about the cache)')
#     p_show.set_defaults(func=func_show)
#     # p_show.add_argument('details', type=bool, help='details help')


    ### subcommand: structure
    p_structure = sub_p.add_parser('structure',
                                   help='show structure of HDF5 or NXDL file')
    p_structure.set_defaults(func=func_structure)
    p_structure.add_argument('infile', help="HDF5 or NXDL file name")
    p_structure.add_argument('-a', 
                        action='store_false', 
                        default=True,
                        dest='show_attributes',
                        help='Do not print attributes of HDF5 file structure')


    ### subcommand: update
    p_update = sub_p.add_parser('update', help='update the local cache of NeXus definitions')
    p_update.set_defaults(func=func_update)
    p_update.add_argument('-f', '--force', 
                               action='store_true', 
                               default=False, 
                               help='force update (if GitHub available)')


    ### subcommand: validate
    p_validate = sub_p.add_parser('validate', help='validate a NeXus file')
    p_validate.add_argument('infile', help="HDF5 or NXDL file name")
    p_validate.set_defaults(func=func_validate)

    return p.parse_args()


def main():
    ''' '''
    args = parse_command_line_arguments()
    args.func(args)


if __name__ == '__main__':
    main()
