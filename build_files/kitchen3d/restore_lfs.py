"""Restore LFS with retries, then checksum-verified upstream media downloads."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.parse import quote
from urllib.request import urlopen

from retry_download import retry


def verified(path, oid, size):
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == oid


def restore_object(url, destination, oid, size):
    if verified(destination, oid, size):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
                temporary = Path(output.name)
                with urlopen(url, timeout=60) as response:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
            if not verified(temporary, oid, size):
                raise ValueError(f'Checksum or size mismatch for {oid}')
            temporary.replace(destination)
            return
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(5 * 2 ** attempt)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--upstream', required=True, help='Official projects.blender.org repository URL')
    parser.add_argument('--media-branch', help='Source fork only: upstream branch; object hashes remain mandatory')
    parser.add_argument('--exclude-tests', action='store_true')
    args = parser.parse_args()
    upstream = args.upstream.removesuffix('.git').rstrip('/')
    if not upstream.startswith('https://projects.blender.org/blender/'):
        parser.error('Only the official Blender server is supported')
    repo = args.repo.resolve()
    git = ['git', '-C', str(repo)]
    pull = [*git, '-c', f'lfs.url={upstream}.git/info/lfs', 'lfs', 'pull']
    if args.exclude_tests:
        pull.append('--exclude=tests/files/**')
    if retry(pull) == 0:
        return 0

    def read(*command):
        return subprocess.check_output([*git, *command], encoding='utf-8').strip()

    def entries():
        return [item for item in json.loads(read('lfs', 'ls-files', '--json'))['files']
                if not (args.exclude_tests and item['name'].startswith('tests/files/'))]

    # A library's HEAD is its pinned upstream commit. Fork-only source commits
    # may not exist upstream, so source fallback uses a branch plus exact hashes.
    kind = 'branch' if args.media_branch else 'commit'
    ref = args.media_branch or read('rev-parse', 'HEAD')
    media = Path(read('rev-parse', '--git-path', 'lfs/objects'))
    if not media.is_absolute():
        media = repo / media
    objects = {item['oid']: item for item in entries()}
    print(f'LFS batch download exhausted retries; restoring {len(objects)} verified '
          'objects from local cache or upstream media.', flush=True)

    def restore(item):
        oid = item['oid']
        url = f'{upstream}/media/{kind}/{quote(ref, safe="")}/{quote(item["name"], safe="/")}'
        restore_object(url, media / oid[:2] / oid[2:4] / oid, oid, item['size'])

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(restore, objects.values()))
    subprocess.run([*git, 'lfs', 'checkout'], check=True)
    missing = [item['name'] for item in entries() if not item['checkout'] or not item['downloaded']]
    if missing:
        raise RuntimeError(f'LFS files remain unavailable: {missing[:10]}')
    print('PASS: LFS fallback restored the required checksum-verified files', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
