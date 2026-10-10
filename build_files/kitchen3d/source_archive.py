#!/usr/bin/env python3
"""Archive materialized tracked source, excluding binary library submodules."""
# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import io
import json
import subprocess
import tarfile

root = Path(__file__).resolve().parents[2]
output = root / 'dist'
output.mkdir(exist_ok=True)
tracked = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root)
libraries = {}
with tarfile.open(output / 'Kitchen3D-source.tar.xz', 'w:xz', preset=3) as archive:
    for record in tracked.decode().split('\0'):
        if not record:
            continue
        metadata, name = record.split('\t', 1)
        if metadata.startswith('160000 '):
            libraries[name] = metadata.split()[1]
            continue
        if name.startswith('tests/files/'):
            continue
        path = root / name
        if path.is_file() and not path.is_symlink():
            with path.open('rb') as file:
                if file.read(100).startswith(b'version https://git-lfs.github.com/spec/v1'):
                    raise RuntimeError(f'Unresolved LFS pointer: {name}')
        archive.add(path, arcname=f'Kitchen3D-source/{name}', recursive=False)
    manifest = json.dumps({
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'library_revisions': libraries,
    }, indent=2).encode('utf-8')
    entry = tarfile.TarInfo('Kitchen3D-source/SOURCE-REVISION.json')
    entry.size = len(manifest)
    archive.addfile(entry, io.BytesIO(manifest))
