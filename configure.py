#!/usr/bin/env python3

# #########################################################################
#
#  2022.04.15 - First version
#
#     May you do good and not evil.
#     May you find forgiveness for yourself and forgive others.
#     May you share freely, never taking more than you give.
#
# #########################################################################
#
#  configure.py -- Implement in Python3 what is unavailable on Windows
#                  (outside of MinGW / Cygwin), the minimal autoconf/automake-
#                  like behaviour of the config shell script provided for use
#                  in Linux / MinGW/Cygwin, macOS. For more, see
#
#                  python3 configure.py --help
#
# #########################################################################

import sys
import os
import os.path
import argparse
import pathlib
from subprocess import STDOUT, PIPE
import subprocess

called_by = 'python'
compiler = None
v = False

DEFAULT_PREFIX = 'C:\\ProgramData'
DEFAULT_MAKENSIS_LOCATION = 'C:\\Program Files (x86)\\NSIS\\makensis.exe'
DEFAULT_SQLITE_WEBPAGE = "https://www.sqlite.org/download.html"


def run_it(*args):
    try:
        p = subprocess.Popen(args, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
        return [line.decode('utf-8') for line in p.stdout.readlines()]
    except FileNotFoundError:
        return None


def drive_letters():
    letters = []
    for ch in range(ord('a'), ord('z') + 1):
        c = chr(ch)
        if os.path.exists('{}:'.format(c)):
            letters.append(c)
    return letters


def find_files_by_name(drive_letter, file_glob):
    print("searching for {} in drive {}:".format(file_glob, drive_letter))
    search_target = r'{}:\{}'.format(drive_letter, file_glob)
    raw_lines = run_it('cmd.exe', '/c', 'dir', '/s', '/b', search_target)
    lines = [line.strip() for line in raw_lines]
    if len(lines) < 1:
        return []
    elif len(lines) == 1 and lines[0] == "File Not Found":
        return []
    return lines


def locate_vcvars_files():
    drives = drive_letters()
    vcvars_32 = []
    vcvars_64 = []
    for d in drives:
        vcvars_32 += find_files_by_name(d, 'vcvars32.*')
        vcvars_64 += find_files_by_name(d, 'vcvars64.*')
    if len(vcvars_32) == 1 and len(vcvars_64) == 1:
        if os.path.dirname(vcvars_32[0]) != os.path.dirname(vcvars_64[0]):
            print("Distinct single batch files for settings were found: {} "
                  "and {}".format(vcvars_32[0], vcvars_64[0]))
            print("but not in the same directory. If this is not acceptable, "
                  "re-run configure")
            print("with the --vcvars-32 and --vcvars-64 switches to choose "
                  "them manually.")
        return (vcvars_32[0], vcvars_64[0])
    elif len(vcvars_32) == 0 and len(vcvars_64) == 0:
        print("No settings batch files (e.g. vcvars32.bat) were found on your "
              "system. Re-run")
        print("configure with the --vcvars-32 and --vcvars-64 switches to "
              "choose them manually.")
        raise Exception("Could not choose vcvars files automatically (0,0)")
    elif len(vcvars_32) == 0:
        print("No settings batch file named like vcvars32.bat could be found "
              "on your system.")
        print("Re-run configure with the --vcvars-32 and --vcvars-64 switches "
              "to choose them manually.")
        print("These vcvars64 files were found: {}".format(
              ", ".join(vcvars_64)))
        message = "Could not choose vcvars files automatically (0,{})"
        message = message.format(len(vcvars_64))
        raise Exception(message)
    elif len(vcvars_64) == 0:
        print("No settings batch file named like vcvars64.bat could be found "
              "on your system.")
        print("Re-run configure with the --vcvars-32 and --vcvars-64 switches "
              "to choose them manually.")
        print("These vcvars32 files were found: {}".format(
              ", ".join(vcvars_32)))
        message = "Could not choose vcvars files automatically ({},0)"
        message = message.format(len(vcvars_32))
        raise Exception(message)
    else:
        print("Multiple settings batch files for 32-bit and 64-bit were found "
              "on your system:")
        print("These vcvars32 files were found: {}".format(
              ", ".join(vcvars_32)))
        print("These vcvars64 files were found: {}".format(
              ", ".join(vcvars_64)))
        print("Re-run configure with the --vcvars-32 and --vcvars-64 switches "
              "to choose them manually.")
        message = "Could not choose vcvars files automatically ({},{})"
        message = message.format(len(vcvars_32), len(vcvars_64))
        raise Exception(message)


def find_lib_in_platform(vcvars_cmd):
    p = subprocess.Popen(['cmd.exe'], stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    commands = ['"{}"'.format(vcvars_cmd), 'lib /?', 'exit']
    cmd = '\n'.join(commands) + '\n'
    send_commands = cmd.encode('utf-8')
    check = p.communicate(input=send_commands, timeout=15)[0]
    check_lines = [line.strip() for line in check.decode('utf-8').split('\n')]
    if any(["'lib' is not" in line for line in check_lines]):
        raise Exception("Running lib after {} did not succeed.".format(
                        vcvars_cmd))
    if not any([line.startswith("Microsoft (R) Library Manager")
                for line in check_lines]):
        print("Running lib after {} seemed to succeed but the result".format(
              vcvars_cmd))
        print("was not recognized. make install and make package may not "
              "succeed.")


def find_make_nsis(loc):
    nsis_lines = run_it(loc, '/VERSION')
    if not nsis_lines:
        if v:
            print("""No makensis was found at {}, 'make package' will not be
available.

MakeNSIS can be downloaded from https://nsis.sourceforge.io/Download -- choose
version 3 or later""".format(loc))
        return None
    nsis_output = nsis_lines[0].strip()
    if nsis_output[0] != 'v':
        print("Unrecognized output from makensis /VERSION: {}".format(
              nsis_output))
        return None
    version_string = nsis_output[1:]
    version_parts = version_string.split('.')
    try:
        if int(version_parts[0]) < 3:
            print("Earlier version of makensis, may not work.")
    except ValueError:
        print("Unrecognized version from makensis /VERSION: {}".format(
              version_string))
        return None
    if v:
        print("Makensis was found at {}, 'make package' will be available.".
              format(loc))
    return loc


def main(argv=sys.argv):
    global v
    run_it('git', 'submodule', 'update', '--init')

    parser = argparse.ArgumentParser(
            description="Configure script for ansak-string on Windows")
    parser.add_argument('--prefix',
                        help='non-default location to install files (does not '
                             'affect \'make package\')',
                        type=str,
                        default=DEFAULT_PREFIX)
    parser.add_argument('--vcvars-32',
                        help='specific vcvars32.cmd file',
                        type=str)
    parser.add_argument('--vcvars-64',
                        help='specific vcvars64.cmd file',
                        type=str)
    parser.add_argument('--make-nsis',
                        help='location of package builder, NullSoft '
                             'Installation System',
                        type=str, default=DEFAULT_MAKENSIS_LOCATION)
    parser.add_argument('--sqlite-download',
                        help='web page that hosts sqlite downloads',
                        type=str, default=DEFAULT_SQLITE_WEBPAGE)
    parser.add_argument('-v', '--verbose',
                        help='more detailed progress messages',
                        action='store_true')

    args = parser.parse_args()
    v = bool(args.verbose)

    # determine ... prefix
    prefix = os.path.realpath(args.prefix)
    if not os.path.isdir(prefix):
        pathlib.Path(prefix).mkdir(parents=True, exist_ok=True)
    if not os.path.isdir(prefix):
        raise Exception("Prefix is not an available directory: {}".format(
                        prefix))

    if args.vcvars_32 is not None:
        if args.vcvars_64 is not None:
            vcvars_32 = str(args.vcvars_32)
            vcvars_64 = str(args.vcvars_64)
            if not os.path.isfile(vcvars_32) and not os.path.isfile(vcvars_64):
                raise Exception("Specified vcvars files do not exist.")
            elif not os.path.isfile(vcvars_32):
                raise Exception("Specified vcvars32 file does not exist.")
            elif not os.path.isfile(vcvars_64):
                raise Exception("Specified vcvars64 file does not exist.")
        else:
            raise Exception("Either specify neither, or both vcvars files. "
                            "(have vcvars32)")
    elif args.vcvars_64 is not None:
        raise Exception("Either specify neither, or both vcvars files. "
                        "(have vcvars32)")
    else:
        (vcvars_32, vcvars_64) = locate_vcvars_files()
    find_lib_in_platform(vcvars_32)
    find_lib_in_platform(vcvars_64)

    make_nsis = find_make_nsis(args.make_nsis)

    # write configvars.py with generator, prefix, compiler values
    repr_download_page = repr(str(args.sqlite_download))
    with open('configvars.py', 'w') as configs:
        print('PREFIX = {}'.format(repr(prefix)), file=configs)
        print('VCVARS_32 = {}'.format(repr(vcvars_32)), file=configs)
        print('VCVARS_64 = {}'.format(repr(vcvars_64)), file=configs)
        print('SQLITE_DL_PAGE = {}'.format(repr_download_page), file=configs)
        print('MAKE_NSIS = {}'.format(repr(make_nsis)), file=configs)
    if v:
        print('Created configvars.py file with values:')
        print('    PREFIX = {}'.format(repr(prefix)))
        print('    VCVARS_32 = {}'.format(repr(vcvars_32)))
        print('    VCVARS_64 = {}'.format(repr(vcvars_64)))
        print('    SQLITE_DL_PAGE = {}'.format(repr_download_page))
        print('    MAKE_NSIS = {}'.format(repr(make_nsis)))

    # write make.cmd running python make.py %*
    with open('make.cmd', 'w') as makebat:
        print('@{} make.py %*'.format(called_by), file=makebat)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append('--help')
    elif not sys.argv[1].startswith('-'):
        called_by = sys.argv[1]
        replacement = [sys.argv[0]]
        replacement = replacement + sys.argv[2:]
        sys.argv = replacement
    main()
