#!/usr/bin/env python3
"""Package a tested install, preserving macOS symlinks and Unix permissions."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def package(install, output, platform, revision):
    executable = {
        'windows-x64': 'kitchen3d.exe',
        'linux-x64': 'kitchen3d',
        'macos-arm64': 'Kitchen 3D.app/Contents/MacOS/Kitchen 3D',
    }[platform]
    if not (install / executable).is_file():
        raise RuntimeError(f'Missing installed executable: {install / executable}')
    if platform != 'macos-arm64':
        suffix = '.exe' if platform == 'windows-x64' else ''
        if not (install / f'kitchen3d-launcher{suffix}').is_file():
            raise RuntimeError('Missing Kitchen 3D launcher')
        if (install / f'blender{suffix}').exists():
            raise RuntimeError('Stale Blender executable: use a clean install directory before packaging')
    if platform == 'linux-x64':
        desktop = (install / 'kitchen3d.desktop').read_text(encoding='utf-8')
        for expected in ('Name=Kitchen 3D', 'Exec=kitchen3d %f', 'Icon=kitchen3d'):
            if expected not in desktop:
                raise RuntimeError(f'Incorrect desktop entry: missing {expected}')
        if not (install / 'kitchen3d.svg').is_file():
            raise RuntimeError('Missing Kitchen 3D desktop icon')
    root = Path(__file__).resolve().parents[2]
    output.mkdir(parents=True, exist_ok=True)
    name = f'Kitchen3D-{platform}'
    # Install already includes third-party notices. Also ship the fork license
    # and exact revision beside the executable, outside the signed app bundle.
    shutil.copy2(root / 'COPYING', install / 'COPYING')
    shutil.copytree(root / 'doc/license', install / 'doc/license', dirs_exist_ok=True)
    (install / 'BUILD.json').write_text(json.dumps({
        'revision': revision, 'platform': platform,
        'configuration': 'build_files/kitchen3d/ci.cmake',
        'source': f'https://github.com/BaerBonesTechnology/blaya/tree/{revision}',
    }, indent=2) + '\n', encoding='utf-8')
    if platform == 'macos-arm64':
        archive = output / f'{name}.zip'
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', str(install), str(archive)], check=True)
    elif platform == 'windows-x64':
        archive = Path(shutil.make_archive(str(output / name), 'zip', install))
    else:
        archive = output / f'{name}.tar.xz'
        with tarfile.open(archive, 'w:xz', preset=3) as tar:
            tar.add(install, arcname=name)
    with archive.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    archive.with_name(archive.name + '.sha256').write_text(f'{digest}  {archive.name}\n')
    print(archive)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--platform', choices=['windows-x64', 'linux-x64', 'macos-arm64'], required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    package(args.install.resolve(), args.output.resolve(), args.platform, args.revision)
