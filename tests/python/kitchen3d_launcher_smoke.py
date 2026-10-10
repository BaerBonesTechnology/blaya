"""Verify the native launcher reaches the branded executable with isolated preferences."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--install', type=Path, required=True)
args = parser.parse_args()
suffix = '.exe' if sys.platform == 'win32' else ''
install = args.install.resolve()
with tempfile.TemporaryDirectory(prefix='kitchen3d-launcher-') as profile:
    marker = Path(profile) / 'launched.txt'
    env = dict(os.environ, BLENDER_USER_CONFIG=profile)
    expression = f'import bpy; from pathlib import Path; Path({str(marker)!r}).write_text(bpy.app.binary_path)'
    # Windows launchers create a hidden console, so verify a fresh child-created
    # marker rather than relying on console output being inherited.
    subprocess.run([
        str(install / f'kitchen3d-launcher{suffix}'),
        '--background', '--factory-startup', '--python-exit-code', '1',
        '--python-expr', expression,
    ], env=env, check=True, timeout=90)
    actual = Path(marker.read_text())
    assert actual.samefile(install / f'kitchen3d{suffix}'), actual
print('PASS: native launcher starts the Kitchen 3D executable')
