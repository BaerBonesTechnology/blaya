"""Download keys ignore checkout state, but invalidate when required objects change."""
import importlib.util
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'cache_keys', Path(__file__).resolve().parents[2] / 'build_files/kitchen3d/cache_keys.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CacheKeysTest(unittest.TestCase):
    def test_utf8_git_output_with_windows_default_encoding(self):
        listing = 'a' * 64 + ' - assets/Ï.blend\n'
        check_output = subprocess.check_output

        def git_output(_command, **kwargs):
            # Exercise real subprocess decoding with a UTF-8 byte (0x8f) that
            # cp1252 cannot decode, even when the test runs on macOS or Linux.
            return check_output([sys.executable, '-c',
                                 f'import sys; sys.stdout.buffer.write({listing.encode("utf-8")!r})'],
                                **kwargs)

        output = io.StringIO()
        with patch.object(subprocess, '_text_encoding', return_value='cp1252'), \
                patch.object(subprocess, 'check_output', side_effect=git_output), \
                patch.object(sys, 'argv', ['cache_keys.py']), contextlib.redirect_stdout(output):
            module.main()
        self.assertEqual(output.getvalue(), f'source={module.source_key(listing)}\n')

    def test_stable_across_materialization_and_order(self):
        a = 'a' * 64 + ' - assets/a.blend\n' + 'b' * 64 + ' * assets/b.blend'
        b = 'b' * 64 + ' - assets/b.blend\n' + 'a' * 64 + ' * assets/a.blend'
        self.assertEqual(module.source_key(a), module.source_key(b))

    def test_only_required_downloads_invalidate_key(self):
        a = 'a' * 64 + ' - assets/a.blend'
        self.assertEqual(module.source_key(a), module.source_key(
            a + '\n' + 'b' * 64 + ' - tests/files/example.blend'))
        self.assertNotEqual(module.source_key(a), module.source_key(a.replace('a' * 64, 'c' * 64)))


if __name__ == '__main__':
    unittest.main()
