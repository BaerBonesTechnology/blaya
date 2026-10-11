#!/usr/bin/env python3
"""Compile the Windows installation wizard from an already tested install."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--install', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
install = args.install.resolve()
output = args.output.resolve()
for name in ('kitchen3d.exe', 'kitchen3d-launcher.exe', 'BUILD.json', 'doc/license/GPL-license.txt'):
    if not (install / name).is_file():
        raise SystemExit(f'Missing packaged file: {name}; run package.py first')
if (install / 'blender.exe').exists() or list(install.glob('unins*.exe')):
    raise SystemExit('Use a clean portable install directory, not an existing Setup installation')
build = json.loads((install / 'BUILD.json').read_text(encoding='utf-8'))
revision = build['revision']
if build['platform'] != 'windows-x64' or not re.fullmatch(r'[0-9a-f]{40}', revision):
    raise SystemExit('Expected Windows x64 BUILD.json with a full source commit')
header = (root / 'source/blender/blenkernel/BKE_blender_version.h').read_text()
version = int(re.search(r'^#define BLENDER_VERSION\s+(\d+)', header, re.M)[1])
patch = int(re.search(r'^#define BLENDER_VERSION_PATCH\s+(\d+)', header, re.M)[1])
compiler = shutil.which('ISCC.exe')
if not compiler:
    candidate = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Inno Setup 6/ISCC.exe'
    if candidate.is_file():
        compiler = str(candidate)
if not compiler:
    raise SystemExit('Inno Setup 6 is required (included on the windows-2022 GitHub runner)')
output.mkdir(parents=True, exist_ok=True)
subprocess.run([
    compiler, f'/DSourceDir={install}', f'/DRepoDir={root}', f'/DOutputDir={output}',
    f'/DAppVersion={version // 100}.{version % 100}.{patch}', f'/DRevision={revision[:12]}',
    str(root / 'build_files/kitchen3d/windows_setup.iss'),
], check=True)
setup = output / 'Kitchen3D-windows-x64-setup.exe'
with setup.open('rb') as file:
    digest = hashlib.file_digest(file, 'sha256').hexdigest()
setup.with_suffix('.exe.sha256').write_text(f'{digest}  {setup.name}\n', encoding='utf-8')
print(setup)
