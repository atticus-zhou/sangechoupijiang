import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path("scripts/verify_comic_v2_user_flow.py")


class ComicV2UserFlowVerifierTests(unittest.TestCase):
    def test_user_flow_verifier_covers_revisions_generation_and_download(self):
        spec = importlib.util.spec_from_file_location("verify_comic_v2_user_flow", SCRIPT_PATH)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        result = module.verify_user_flow(
            fixture_path=Path("tests/fixtures/comic_v2_sample.json"),
            output_dir=Path("output/comic_v2_user_flow_verification"),
        )

        self.assertEqual(result["final_stage"], "ready_for_handoff")
        self.assertEqual(result["visual_revisions"], 1)
        self.assertEqual(result["asset_revisions"], 1)
        self.assertGreater(result["generated_images"], 0)
        self.assertGreater(result["download_bytes"], 1000)
        self.assertTrue(result["handoff_manifest_uri"].endswith("_handoff_manifest.json"))
        self.assertTrue(result["handoff_manifest_artifact"])
        self.assertTrue(result["handoff_manifest_production_lineage"])
        self.assertTrue(result["production_lineage_handoff_fields"])
        self.assertGreater(result["event_count"], 0)
        self.assertEqual(result["task_status"], "completed")
        self.assertTrue(result["delivery_audit"]["handoff_ready"])
        self.assertIn("visual_bible_review", result["visited_stages"])
        self.assertIn("asset_review", result["visited_stages"])
        self.assertIn("document_generation", result["visited_stages"])
        self.assertIn("ready_for_handoff", result["visited_stages"])


if __name__ == "__main__":
    unittest.main()
