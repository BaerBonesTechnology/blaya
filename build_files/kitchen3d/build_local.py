"""Build, install and test Kitchen 3D locally without packaging or publishing."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys


def main():
    source = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=source.parent / 'build_kitchen3d_5.4_alpha')
    parser.add_argument('--install-dir', type=Path)
    parser.add_argument('--jobs', type=int, default=min(6, os.cpu_count() or 1))
    parser.add_argument('--cmake', default='cmake')
    parser.add_argument('--optix-root', type=Path, help='Windows: directory containing the OptiX include folder')
    parser.add_argument('--prepare', action='store_true', help='Fetch upstream LFS assets and pinned platform libraries')
    parser.add_argument('--dry-run', action='store_true', help='Print commands without running them')
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    system = platform.system()
    machine = platform.machine().lower()
    libraries = {('Windows', 'amd64'): 'windows_x64', ('Windows', 'x86_64'): 'windows_x64',
                 ('Linux', 'x86_64'): 'linux_x64', ('Darwin', 'arm64'): 'macos_arm64'}
    library = libraries.get((system, machine))
    if library is None:
        parser.error(f'Unsupported platform: {system} {machine}')
    build = args.build_dir.resolve()
    install = (args.install_dir or build / 'install').resolve()
    if build == source or source in build.parents or install == source or source in install.parents:
        parser.error('Use build and install directories outside the source checkout')

    def run(command):
        command = [str(item) for item in command]
        print(shlex.join(command), flush=True)
        if not args.dry_run:
            subprocess.run(command, cwd=source, check=True)

    if args.prepare:
        run(['git', '-c', 'lfs.url=https://projects.blender.org/blender/blender.git/info/lfs',
             'lfs', 'pull', '--exclude=tests/files/**'])
        run(['git', 'submodule', 'update', '--init', '--checkout', '--', f'lib/{library}'])
        run(['git', '-C', f'lib/{library}', 'lfs', 'pull'])
    configure = [args.cmake, '-S', source, '-B', build, '-G', 'Ninja',
                 '-C', source / 'build_files/kitchen3d/local.cmake',
                 '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_INSTALL_PREFIX={install}',
                 f'-DTEST_PYTHON_EXE={sys.executable}']
    if args.optix_root:
        configure.append(f'-DOPTIX_ROOT_DIR={args.optix_root.resolve()}')
    run(configure)
    run([args.cmake, '--build', build, '--target', 'install', '--parallel', args.jobs])
    ctest = str(Path(args.cmake).with_name('ctest.exe' if system == 'Windows' else 'ctest'))
    run([ctest, '--test-dir', build, '-C', 'Release', '-L', 'kitchen3d',
         '--output-on-failure', '--no-tests=error', '--parallel', '1'])
    print(f'Local application directory: {install}')


if __name__ == '__main__':
    main()
