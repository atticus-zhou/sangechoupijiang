import importlib.util
import json
import subprocess
import sys
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
        self.assertEqual(result["embedded_images"], 7)
        self.assertTrue(result["handoff_manifest_exists"])
        self.assertEqual(result["handoff_manifest_assets"], 3)
        self.assertEqual(result["handoff_manifest_images"], 7)
        self.assertEqual(result["handoff_manifest_shots"], 2)
        self.assertTrue(result["handoff_manifest_image_prompts"])
        self.assertTrue(result["handoff_manifest_image_production_roles"])
        self.assertTrue(result["handoff_manifest_asset_identity_fields"])
        self.assertTrue(result["handoff_manifest_asset_baseline_chain"])
        self.assertTrue(result["handoff_manifest_shot_reference_images"])
        self.assertTrue(result["handoff_manifest_shot_execution_notes"])
        self.assertTrue(result["handoff_manifest_production_lineage"])
        self.assertTrue(result["handoff_manifest_lineage_handoff_fields"])
        self.assertTrue(result["handoff_manifest_downstream_quick_start"])
        self.assertEqual(result["handoff_manifest_downstream_quick_start_steps"], 5)
        self.assertTrue(result["word_canvas_agent_handoff"])
        self.assertTrue(result["word_canvas_asset_file_references"])
        self.assertLessEqual(result["max_table_columns"], 2)
        self.assertEqual(result["missing_image_asset_ids"], [])
        self.assertEqual(result["structural_errors"], [])

    def test_cli_json_exposes_delivery_quality_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--fixture",
                    str(FIXTURE_PATH),
                    "--output-dir",
                    tmp,
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        payload = json.loads(completed.stdout)
        self.assertTrue(payload["handoff_ready"])
        self.assertEqual(payload["asset_count"], 3)
        self.assertEqual(payload["shot_count"], 2)
        self.assertEqual(payload["embedded_images"], 7)
        self.assertTrue(payload["handoff_manifest_shot_production_package"])
        self.assertTrue(payload["handoff_manifest_image_production_roles"])
        self.assertTrue(payload["handoff_manifest_downstream_quick_start"])
        self.assertEqual(payload["handoff_manifest_downstream_quick_start_steps"], 5)
        self.assertTrue(payload["word_canvas_asset_file_references"])

    def test_cli_markdown_is_portfolio_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--fixture",
                    str(FIXTURE_PATH),
                    "--output-dir",
                    tmp,
                    "--format",
                    "markdown",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertIn("Comic V2 Delivery Audit", completed.stdout)
        self.assertIn("Delivery Counts", completed.stdout)
        self.assertIn("Quality Gates", completed.stdout)
        self.assertIn("Downstream quick-start steps: 5", completed.stdout)
        self.assertIn("Downstream quick-start playbook", completed.stdout)
        self.assertIn("Word canvas agent handoff checklist", completed.stdout)


if __name__ == "__main__":
    unittest.main()
