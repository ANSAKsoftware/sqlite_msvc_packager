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
#  make.py -- Implement in Python3 what is unavailable on Windows (outside of
#             MinGW / Cygwin), the minimal Makefile-like behaviour of all
#             install, uninstall and a few other things. For more, see
#
#             python3 make.py help
#
# #########################################################################

import sys
import os
import os.path
import argparse
import hashlib
import itertools
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

try:
    from configvars import PREFIX, VCVARS_32, VCVARS_64, MAKE_NSIS, SQLITE_DL_PAGE
except ModuleNotFoundError:
    print("run .\\configure.cmd before doing make")
    sys.exit(1)


SQLITE_ROOT = 'https://sqlite.org'
DOWNLOAD_PAGE = 'download.html'
CMD = 'c:\\windows\\system32\\cmd.exe'
C = '/c'
CMAKE = 'cmake'
BUILD = '--build'
GRANDPARENT = '..\\..'
CONF = '-C'
GEN = '-G'
ARCH = '-A'
PACKAGE_NAME = 'sqlite3-for-msvc-setup.exe'


class Proc:

    def __init__(self, *args, consume=False, env=None, cwd=None):
        try:
            self.lines_ = []
            self.rc_ = None
            self.consume_ = consume
            extras = {'stdin': subprocess.PIPE, 'stdout': subprocess.PIPE,
                      'stderr': subprocess.STDOUT} if consume else {}
            if cwd:
                extras['cwd'] = cwd
            if env:
                env.update(os.environ)
                extras['env'] = env
            self.p_ = subprocess.Popen(args, **extras)
        except FileNotFoundError:
            self.p_ = None
            self.rc_ = 9009

    def rc(self):
        if self.rc_ is not None:
            return self.rc_
        if self.consume_:
            self.lines_ += self.p_.stdout.readlines()
        self.rc_ = self.p_.wait()
        return self.rc_

    def lines(self):
        if self.rc_ is None and self.consume_:
            self.lines_ += self.p_.stdout.readlines()
        return self.lines_

    def run(self):
        return self.rc()


def source_is_newer(than_file, other=None):
    if not os.path.isfile(than_file):
        return True

    # get changed-date of than_file
    than_file_stamp = os.path.getmtime(than_file)

    def newer(f):
        return os.path.getmtime(f) > than_file_stamp

    iter_these = [('configvars.py',
                   os.path.join('NSIS', 'sqlite_packager.nsi'))]
    if other is not None:
        iter_these.append(other)
    scan_these = itertools.chain(*iter_these)

    return any(newer(p) for p in scan_these)


def run_or_die(action):
    r = action()
    if r != 0:
        sys.exit(r)


def create_dirs(dirs):
    for d in dirs:
        try:
            os.mkdir(d)
        except FileExistsError as efef:
            if not os.path.isdir(d):
                return efef.args[0]
        except PermissionError as epe:
            return epe.args[0]
    return 0


def rm_f(path):
    if os.path.isdir(os.path.dirname(path)) and os.path.isfile(path):
        os.unlink(path)


class MakerDirs:

    def install_dests():
        include_root = os.path.join(PREFIX, 'include')
        bin_root = os.path.join(PREFIX, 'bin')
        lib_root = os.path.join(PREFIX, 'lib')
        lib_win32_root = os.path.join(lib_root, 'Win32')
        lib_x64_root = os.path.join(lib_root, 'x64')
        return {'include_root': include_root,
                'bin_root': bin_root,
                'lib_root': lib_root,
                'lib_win32_root': lib_win32_root,
                'lib_x64_root': lib_x64_root}

    def nsis_dests():
        if MAKE_NSIS:
            nsis_root = os.path.join('build', 'nsis')
            nsis_include = os.path.join(nsis_root, 'include')
            nsis_bin_root = os.path.join(nsis_root, 'bin')
            nsis_lib_root = os.path.join(nsis_root, 'lib')
            nsis_lib_win32_root = os.path.join(nsis_lib_root, 'Win32')
            nsis_lib_x64_root = os.path.join(nsis_lib_root, 'x64')
            return {'nsis': nsis_root,
                    'include': nsis_include,
                    'bin': nsis_bin_root,
                    'lib': nsis_lib_root,
                    'lib_win32': nsis_lib_win32_root,
                    'lib_x64': nsis_lib_x64_root}
        else:
            return {}


class Maker:

    def __init__(self):
        self.build_dir_ = 'build'
        self.win32_dir_ = os.path.join(self.build_dir_, 'Win32')
        self.x64_dir_ = os.path.join(self.build_dir_, 'x64')
        self.amalgam_dir_ = None
        self.dll_win32_dir = os.path.join(self.build_dir_, 'dll-win32')
        self.dll_x64 = os.path.join(self.build_dir_, 'dll-x64')
        self.done_ = set()
        self.step_performed_ = False
        self.package_path_ = os.path.join('build', PACKAGE_NAME)
        self.v_ = False

    def valid_order(raw_targets):
        valid = []
        if any(t == 'help' for t in raw_targets):
            return ['help']
        if any(t == 'clean' for t in raw_targets):
            valid.append('clean')
        for t in raw_targets:
            if t != 'clean':
                valid.append(t)
        if not valid:
            return ['all']
        return valid

    def make_all(self):
        create_dirs([self.build_dir_, self.win32_dir_, self.x64_dir_])

        if not source_is_newer('build\\all.touch'):
            self.done_.add('all')
            return

        rm_f(os.path.join(self.build_dir_, 'sqlite3.h'))
        rm_f(os.path.join(self.build_dir_, 'sqlite3ext.h'))
        rm_f(os.path.join(self.win32_dir_, 'sqlite3.def'))
        rm_f(os.path.join(self.win32_dir_, 'sqlite3.dll'))
        rm_f(os.path.join(self.win32_dir_, 'sqlite3-Win32.dll'))
        rm_f(os.path.join(self.x64_dir_, 'sqlite3.def'))
        rm_f(os.path.join(self.x64_dir_, 'sqlite3-x64.dll'))
        for fn in os.listdir(self.build_dir_):
            if fn.endswith('zip'):
                rm_f(os.path.join(self.build_dir_, fn))
            elif fn.startswith('sqlite-amalgamation'):
                Proc(CMD, C, 'rmdir', '/s', '/q', os.path.join(self.build_dir_, fn)).run()

        # download the things
        with urllib.request.urlopen('/'.join([SQLITE_ROOT, DOWNLOAD_PAGE])) as u:
            html_lines = u.read().decode('utf-8').split('\n')
        # parse out the three lines
        download_lines = [line for line in html_lines
                          if line.startswith('PRODUCT') and
                             (line.find('dll-win') >= 0 or
                              line.find('amalgam') >= 0)]

        tSources = [l.split(',') for l in download_lines]
        targets = [{'suburl':l[2], 'size':int(l[3]), 'sha3sum':l[4]} for l in tSources]

        def downloadTarget(dt):
            dt['fname'] = os.path.basename(dt["suburl"])
            with urllib.request.urlopen('/'.join([SQLITE_ROOT, dt["suburl"]])
                                       ) as u:
                payload = u.read()
            if len(payload) != dt["size"]:
                message = "{} downloaded but wrong size: {} vs. {}"
                message = message.format(dt['fname'], len(payload), dt.size)
                raise Exception(message)
            sha3 = hashlib.sha3_256()
            sha3.update(payload)
            if sha3.digest().hex() != dt["sha3sum"]:
                message = "{} downloaded but wrong hash: {} vs. {}"
                message = message.format(dt['fname'], sha3.digest().hex(),
                                         dt.sha3sum)
                raise Exception(message)
            dt['destfile'] = os.path.join(self.build_dir_, dt["fname"])
            with open(dt['destfile'], 'wb') as f:
                f.write(payload)

        # download the three zip files and validate them
        for t in targets:
            downloadTarget(t)

        # unpack the downloads
        for t in targets:
            if t["fname"].find('dll-win32') >= 0:
                with zipfile.ZipFile(t["destfile"], 'r') as zipf:
                    zipf.extractall(self.win32_dir_)
            elif t["fname"].find('dll-win64') >= 0:
                with zipfile.ZipFile(t["destfile"], 'r') as zipf:
                    zipf.extractall(self.x64_dir_)
            elif t["fname"].find('amalgam') >= 0:
                with zipfile.ZipFile(t["destfile"], 'r') as zipf:
                    zipf.extractall(self.build_dir_)
                name = [name for name in os.listdir(self.build_dir_) if name.startswith('sqlite') and not 'dll-' in name][0]
                fn_sqlite3_h = os.path.join(self.build_dir_, name, 'sqlite3.h')
                fn_sqlite3ext_h = os.path.join(self.build_dir_, name,
                                               'sqlite3ext.h')
                shutil.copy2(fn_sqlite3_h, self.build_dir_)
                shutil.copy2(fn_sqlite3ext_h, self.build_dir_)

        # nobble the .def files
        def nobbleOneDefFile(theDir, theType):
            outFileName = os.path.join(theDir, 'new-sqlite3.def')
            inFileName = os.path.join(theDir, 'sqlite3.def')
            with open(outFileName, 'w') as outF:
                print("LIBRARY sqlite3-{}".format(theType), file=outF)
                with open(inFileName, 'r') as inF:
                    residue = inF.read()
                outF.write(residue)
            os.unlink(inFileName)
            os.rename(outFileName, inFileName)

        nobbleOneDefFile(self.win32_dir_, 'Win32')
        nobbleOneDefFile(self.x64_dir_, 'x64')

        # rename the dlls
        os.rename(os.path.join(self.win32_dir_, 'sqlite3.dll'),
                  os.path.join(self.win32_dir_, 'sqlite3-Win32.dll'))
        os.rename(os.path.join(self.x64_dir_, 'sqlite3.dll'),
                  os.path.join(self.x64_dir_, 'sqlite3-x64.dll'))

        # lib the .defs into .libs
        def defIntoLib(theDir, theSetup, theMachine):
            p = subprocess.Popen(['cmd.exe'], cwd=theDir, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            commands = [theSetup,
                        'lib /DEF:sqlite3.def /MACHINE:{} /OUT:sqlite3.lib',
                        'exit']
            cmd = '\n'.join(commands) + '\n'
            send_commands = cmd.encode('utf-8')
            check = p.communicate(input=send_commands, timeout=15)[0]
            check_lines = [line.strip() for line in
                           check.decode('utf-8').split('\n')]
            if not any(['Creating library' in line for line in check_lines]):
                print("Expected message about \"Creating library\" was not "
                      "found in the output:")
                for line in check_lines:
                    print("   {}".format(line))
            if not os.path.isfile(os.path.join(theDir, 'sqlite3.lib')):
                message = "sqlite3.lib was not created for {} in {}".format(
                          theDir, theMachine)
                raise Exception(message)

        defIntoLib(self.win32_dir_, VCVARS_32, 'X86')
        defIntoLib(self.x64_dir_, VCVARS_64, 'X64')
        self.done_.add('all')
        self.step_performed_ = True
        with open('build\\all.touch', 'w') as f:
            print("Done!", file=f)

    def install(self):
        if 'all' not in self.done_:
            self.make_all()

        paths = MakerDirs.install_dests()
        dirs_made = create_dirs(paths.values())
        if dirs_made != 0:
            sys.exit(dirs_made)
        try:
            shutil.copy2(os.path.join('build', 'Win32', 'sqlite3.lib'),
                         paths['lib_win32_root'])
            shutil.copy2(os.path.join('build', 'x64', 'sqlite3.lib'),
                         paths['lib_x64_root'])
            shutil.copy2(os.path.join('build', 'sqlite3.h'), paths['include_root'])
            shutil.copy2(os.path.join('build', 'sqlite3ext.h'),
                         paths['include_root'])
            shutil.copy2(os.path.join('build', 'Win32', 'sqlite3-Win32.dll'),
                         paths['bin_root'])
            shutil.copy2(os.path.join('build', 'x64', 'sqlite3-x64.dll'),
                         paths['bin_root'])
            self.step_performed_ = True
        except PermissionError as epe:
            print("{} for prefix {} must be run from an {} shell".format(
                  'make install', PREFIX, 'Admin-privilege'))
            sys.exit(epe.args[0])

    def uninstall(self):
        paths = MakerDirs.install_dests()

        def rmdirIfEmpty(empty_dir):
            if os.path.isdir(empty_dir):
                files_in_include = os.listdir(empty_dir)
                if not files_in_include:
                    os.rmdir(empty_dir)
        try:
            rm_f(os.path.join(paths['include_root'], 'sqlite3.h'))
            rm_f(os.path.join(paths['include_root'], 'sqlite3ext.h'))
            rmdirIfEmpty(paths['include_root'])

            rm_f(os.path.join(paths['lib_win32_root'], 'sqlite3.lib'))
            rmdirIfEmpty(paths['lib_win32_root'])
            rm_f(os.path.join(paths['lib_x64_root'], 'sqlite3.lib'))
            rmdirIfEmpty(paths['lib_x64_root'])

            rm_f(os.path.join(paths['bin_root'], 'sqlite3-Win32.dll'))
            rm_f(os.path.join(paths['bin_root'], 'sqlite3-x64.dll'))
            rmdirIfEmpty(paths['bin_root'])
            self.step_performed_ = True
        except PermissionError as epe:
            print("{} for prefix {} must be run from an {} shell".format(
                  'make uninstall', PREFIX, 'Admin-privilege'))
            sys.exit(epe.args[0])

    def package(self):
        if not MAKE_NSIS:
            print("makensis could not be located, package target not " +
                  "available.")
            sys.exit(1)
        if 'all' not in self.done_:
            self.make_all()

        # dependency check of product vs. its sources
        if not source_is_newer(self.package_path_, Path('NSIS').glob('*')):
            return

        # prep the directories
        nsis_dests = MakerDirs.nsis_dests()
        assert nsis_dests
        dir_make = create_dirs(nsis_dests.values())
        if dir_make != 0:
            sys.exit(dir_make)

        # copy things to the directories
        for f in os.listdir('NSIS'):
            shutil.copy2(os.path.join('NSIS', f), nsis_dests['nsis'])

        shutil.copy2(os.path.join(self.build_dir_, "sqlite3.h"), nsis_dests['include'])
        shutil.copy2(os.path.join(self.build_dir_, "sqlite3ext.h"), nsis_dests['include'])

        shutil.copy2(os.path.join(self.win32_dir_, 'sqlite3.lib'), nsis_dests['lib_win32'])
        shutil.copy2(os.path.join(self.x64_dir_, 'sqlite3.lib'), nsis_dests['lib_x64'])

        shutil.copy2(os.path.join(self.win32_dir_, 'sqlite3-Win32.dll'), nsis_dests['bin'])
        shutil.copy2(os.path.join(self.x64_dir_, 'sqlite3-x64.dll'), nsis_dests['bin'])

        # create the install set, move it to ./build
        def run_nsis():
            return Proc(CMD, C, MAKE_NSIS, 'sqlite_packager.nsi',
                        cwd=nsis_dests['nsis']).run()

        run_or_die(run_nsis)
        shutil.copy2(os.path.join(nsis_dests['nsis'], PACKAGE_NAME), 'build')
        self.step_performed_ = True

    def clean(self):
        def deleteThese(paths):
            for path in paths:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    rm_f(path)

        deleteThese([self.win32_dir_, self.x64_dir_,
                     MakerDirs.nsis_dests()['nsis'], self.package_path_])
        deleteThese(MakerDirs.touch_files())

        self.step_performed_ = True

    def scrub(self):
        if os.path.isdir('build'):
            Proc(CMD, C, 'rmdir', '/s', '/q', 'build').run()
        rm_f('configvars.py')
        if os.path.isdir('__pycache__'):
            Proc(CMD, C, 'rmdir', '/s', '/q', '__pycache__').run()
        self.step_performed_ = True

    def help(self):
        print("Makefile simluator for ease-of-deployment on Windows in Win32")
        print("  * help: this message")
        print("  * all: (default target) compile of the libraries (Release)")
        print("  * install: deploy headers and libraries to prefix")
        print("  * uninstall: remove the headers and libraries at prefix")
        print("  * package: build an installer for this source code, place " +
              "it in .\\build (unaffected by prefix setting)")
        print("Run .\\configure.cmd before running .\\make. There are some")
        print("important settings to be determined there.")
        self.step_performed_ = True

    targets = {"all": make_all, "install": install, "uninstall": uninstall,
               "package": package, "clean": clean, "scrub": scrub,
               "help": help}

    def process(self, args):
        self.v_ = bool(args.verbose)
        for target in Maker.valid_order(args.targets):
            assert target in Maker.targets
            Maker.targets[target](self)
        if not self.step_performed_:
            print('Nothing to do for targets, {}'.format(repr(args.targets)))


def main():
    parser = argparse.ArgumentParser(
                 description="Make script for ansak-string on Windows")
    parser.add_argument('-v', '--verbose',
                        help='more detailed progress messages',
                        action='store_true')
    targets_prompt = 'Things to build. If nothing specified, "all" '
    targets_prompt += 'is assumed. Possible values are: {}'.format(
                      str(Maker.targets.keys()))
    parser.add_argument('targets', help=targets_prompt, type=str, nargs='*')

    Maker().process(parser.parse_args())


if __name__ == '__main__':
    main()
