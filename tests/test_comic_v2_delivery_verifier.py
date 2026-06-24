import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path("scripts/verify_comic_v2_delivery.py")
FIXTURE_PATH = Path("tests/fixtures/comic_v2_sample.json")


class ComicV2DeliveryVerifierTests(unittest.TestCase):
    def test_fixed_sample_builds_a_complete_page_based_canvas(self):
        spec = importlib.util.spec_from_file_location("verify_comic_v2_delivery", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            result = module.verify_delivery(FIXTURE_PATH, Path(tmp))

        self.assertTrue(result["handoff_ready"])
        self.assertEqual(result["asset_count"], 3)
        self.assertEqual(result["shot_count"], 2)
        self.assertEqual(result["embedded_images"], 3)
        self.assertLessEqual(result["max_table_columns"], 2)
        self.assertEqual(result["missing_image_asset_ids"], [])
        self.assertEqual(result["structural_errors"], [])


if __name__ == "__main__":
    unittest.main()
