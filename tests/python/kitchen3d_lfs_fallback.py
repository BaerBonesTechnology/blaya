"""Fallback accepts only exact LFS objects, including when the server is unavailable."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'build_files/kitchen3d'))
import restore_lfs


class LfsFallbackTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / 'objects' / 'object'
        self.data = b'pinned dependency content'
        self.oid = hashlib.sha256(self.data).hexdigest()

    def restore(self):
        restore_lfs.restore_object('https://example.invalid/object', self.target,
                                   self.oid, len(self.data))

    def test_fallback_downloads_verified_content(self):
        with patch.object(restore_lfs, 'urlopen', return_value=io.BytesIO(self.data)):
            self.restore()
        self.assertEqual(self.target.read_bytes(), self.data)

    def test_cached_content_survives_outage(self):
        self.target.parent.mkdir()
        self.target.write_bytes(self.data)
        with patch.object(restore_lfs, 'urlopen', side_effect=OSError('502')) as download:
            self.restore()
        download.assert_not_called()

    def test_mismatched_content_never_enters_cache(self):
        with patch.object(restore_lfs, 'urlopen', side_effect=lambda *a, **k: io.BytesIO(b'wrong')), \
                patch.object(restore_lfs.time, 'sleep') as sleep:
            with self.assertRaisesRegex(ValueError, 'Checksum or size mismatch'):
                self.restore()
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.iterdir()), [])
        self.assertEqual(sleep.call_count, 2)

    def test_temporary_media_failure_recovers(self):
        with patch.object(restore_lfs, 'urlopen', side_effect=[OSError('502'), io.BytesIO(self.data)]), \
                patch.object(restore_lfs.time, 'sleep') as sleep:
            self.restore()
        self.assertEqual(self.target.read_bytes(), self.data)
        sleep.assert_called_once_with(5)


if __name__ == '__main__':
    unittest.main()
