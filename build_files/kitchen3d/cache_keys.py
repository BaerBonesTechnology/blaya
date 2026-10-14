"""Content-based keys for downloaded LFS objects (no branch names or credentials)."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
import hashlib
from pathlib import Path
import subprocess


def source_key(listing):
    objects = []
    for line in listing.splitlines():
        oid, _status, path = line.split(' ', 2)
        if not path.startswith('tests/files/'):
            objects.append(f'{oid} {path}')
    return hashlib.sha256('\n'.join(sorted(objects)).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', choices=('windows_x64', 'linux_x64', 'macos_arm64'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]

    def git(*arguments):
        # Git LFS emits UTF-8 paths, regardless of the Windows ANSI code page.
        return subprocess.check_output(
            ['git', *arguments], cwd=root, encoding='utf-8').strip()

    print(f"source={source_key(git('lfs', 'ls-files', '--long'))}")
    if args.library:
        print(f"library={git('rev-parse', f'HEAD:lib/{args.library}')}")


if __name__ == '__main__':
    main()
