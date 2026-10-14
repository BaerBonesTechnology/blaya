"""Retry resumable CI download commands with bounded exponential backoff."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
import subprocess
import sys
import time


def retry(command, attempts=4, delay=15):
    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.call(command)
        except OSError as error:
            print(f'Cannot start download command: {error}', file=sys.stderr, flush=True)
            return 127
        if result == 0:
            return 0
        if result < 0:
            return 128 - result
        if attempt == attempts:
            print(f'Download failed after {attempts} attempts (exit {result}).',
                  file=sys.stderr, flush=True)
            return result
        wait = min(delay * 2 ** (attempt - 1), 60)
        print(f'Download attempt {attempt}/{attempts} failed (exit {result}); '
              f'retrying in {wait}s.', file=sys.stderr, flush=True)
        time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempts', type=int, default=4)
    parser.add_argument('--delay', type=float, default=15)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command or args.attempts < 1 or args.delay < 0:
        parser.error('Provide a command, positive attempt count and nonnegative delay')
    return retry(command, args.attempts, args.delay)


if __name__ == '__main__':
    sys.exit(main())
