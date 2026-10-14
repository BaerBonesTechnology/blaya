"""Retry failures without hiding exhausted retries or repeating successful work."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import call, patch

spec = importlib.util.spec_from_file_location(
    'retry_download', Path(__file__).resolve().parents[2] / 'build_files/kitchen3d/retry_download.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DownloadRetryTest(unittest.TestCase):
    def test_temporary_failures_recover(self):
        with patch.object(module.subprocess, 'call', side_effect=[2, 2, 0]) as run, \
                patch.object(module.time, 'sleep') as sleep:
            self.assertEqual(module.retry(['git', 'lfs', 'pull']), 0)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(15), call(30)])

    def test_exhaustion_keeps_failure(self):
        with patch.object(module.subprocess, 'call', return_value=2) as run, \
                patch.object(module.time, 'sleep') as sleep:
            self.assertEqual(module.retry(['git', 'lfs', 'pull']), 2)
        self.assertEqual(run.call_count, 4)
        self.assertEqual(sleep.call_args_list, [call(15), call(30), call(60)])

    def test_success_is_not_repeated(self):
        with patch.object(module.subprocess, 'call', return_value=0) as run, \
                patch.object(module.time, 'sleep') as sleep:
            self.assertEqual(module.retry(['git', 'lfs', 'pull']), 0)
        run.assert_called_once()
        sleep.assert_not_called()

    def test_missing_program_is_not_retried(self):
        with patch.object(module.subprocess, 'call', side_effect=FileNotFoundError('missing')) as run, \
                patch.object(module.time, 'sleep') as sleep:
            self.assertEqual(module.retry(['missing']), 127)
        run.assert_called_once()
        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
