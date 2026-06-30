import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_product_readiness.py")


class ProductReadinessScriptTests(unittest.TestCase):
    def test_script_outputs_json_readiness_audit(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["office_id"], "comic_production")
        self.assertEqual(payload["status"], "ready_without_demo")
        self.assertTrue(payload["checks"])

    def test_script_outputs_markdown_readiness_audit(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("AI 漫剧制片办公室真实产品 readiness", result.stdout)
        self.assertIn("完整工作流状态", result.stdout)

    def test_script_can_run_deterministic_runtime_verification(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json", "--run-e2e"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)
        runtime = payload["runtime_verification"]

        self.assertEqual(runtime["delivery"]["status"], "passed")
        self.assertTrue(runtime["delivery"]["handoff_ready"])
        self.assertGreater(runtime["delivery"]["embedded_images"], 0)
        self.assertTrue(runtime["delivery"]["handoff_manifest_exists"])
        self.assertEqual(runtime["delivery"]["handoff_manifest_assets"], runtime["delivery"]["asset_count"])
        self.assertEqual(runtime["delivery"]["handoff_manifest_images"], runtime["delivery"]["embedded_images"])
        self.assertEqual(runtime["delivery"]["handoff_manifest_shots"], runtime["delivery"]["shot_count"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_image_prompts"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_asset_identity_fields"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_asset_baseline_chain"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_shot_reference_images"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_shot_execution_notes"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_production_lineage"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_lineage_handoff_fields"])
        self.assertTrue(runtime["delivery"]["word_canvas_agent_handoff"])
        self.assertTrue(runtime["delivery"]["word_canvas_asset_file_references"])
        self.assertEqual(runtime["user_flow"]["status"], "passed")
        self.assertEqual(runtime["user_flow"]["final_stage"], "ready_for_handoff")
        self.assertTrue(runtime["user_flow"]["handoff_manifest_asset_baseline_chain"])
        self.assertTrue(runtime["user_flow"]["production_lineage_handoff_fields"])
        self.assertGreater(runtime["user_flow"]["download_bytes"], 1000)
        self.assertGreater(runtime["user_flow"]["generated_images"], 0)

    def test_markdown_mentions_runtime_verification_when_enabled(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown", "--run-e2e"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("运行时验证", result.stdout)
        self.assertIn("ready_for_handoff", result.stdout)


if __name__ == "__main__":
    unittest.main()
