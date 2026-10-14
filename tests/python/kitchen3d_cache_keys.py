"""Download keys ignore checkout state, but invalidate when required objects change."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'cache_keys', Path(__file__).resolve().parents[2] / 'build_files/kitchen3d/cache_keys.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CacheKeysTest(unittest.TestCase):
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
