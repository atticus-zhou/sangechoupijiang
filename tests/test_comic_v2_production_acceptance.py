import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_comic_v2_production_acceptance.py")
FIXTURE = Path("tests/fixtures/comic_v2_sample.json")
UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class ComicV2ProductionAcceptanceTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.spec_from_file_location("verify_comic_v2_production_acceptance", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_fixture_acceptance_separates_demo_from_real_downstream(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            result = module.verify_production_acceptance(FIXTURE, Path(tmp))

        self.assertEqual(result["status"], "passed", result["failed_check_ids"])
        self.assertTrue(result["accepted_for_public_demo"])
        self.assertFalse(result["accepted_for_real_downstream"])
        self.assertEqual(result["downstream_status"], "structure_demo_only")
        self.assertEqual(result["claim_level"], "demo_structure_only")
        self.assertEqual(result["quality_claim"], "demo_structure_verified")
        self.assertFalse(result["production_quality_verified"])
        self.assertEqual(result["visual_evidence_level"], "fixture_only")
        self.assertEqual(result["failure_count"], 0)

        checks = {item["id"]: item for item in result["checklist"]}
        self.assertEqual(
            set(checks),
            {
                "structure_handoff",
                "asset_identity_chain",
                "clean_base_assets",
                "director_prompts",
                "word_canvas_and_manifest",
                "real_quality_boundary",
            },
        )
        for check in checks.values():
            self.assertTrue(check["passed"], check)
            self.assertTrue(check["evidence"])

        self.assertIn("结构演示", result["human_decision"])
        self.assertIn("不能说已经达到真实模型画质", result["human_decision"])
        self.assertIn("can_claim_real_quality=True", result["operator_next_step"])
        self.assertEqual(result["image_quality_summary"]["total_images"], 7)
        self.assertEqual(result["image_quality_summary"]["waste_or_rework_images"], 0)
        self.assertEqual(result["prompt_quality_summary"]["status"], "ready")
        self.assertEqual(result["prompt_quality_summary"]["issue_count"], 0)
        self.assertFalse(result["downstream_handoff_decision"]["handoff_allowed"])
        self.assertGreater(result["real_quality_promotion_gate"]["blocking_count"], 0)

    def test_cli_json_outputs_operator_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixture",
                    str(FIXTURE),
                    "--output-dir",
                    tmp,
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=UTF8_ENV,
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "comic_v2_production_acceptance")
        self.assertFalse(payload["calls_real_models"])
        self.assertTrue(payload["accepted_for_public_demo"])
        self.assertFalse(payload["accepted_for_real_downstream"])
        self.assertEqual(payload["downstream_status"], "structure_demo_only")
        self.assertIn("word_canvas", payload["evidence"])
        self.assertEqual(payload["failed_check_ids"], [])

    def test_cli_markdown_is_human_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixture",
                    str(FIXTURE),
                    "--output-dir",
                    tmp,
                    "--format",
                    "markdown",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=UTF8_ENV,
            )

        self.assertIn("AI Comic V2 Production Acceptance", completed.stdout)
        self.assertIn("Public demo accepted: `True`", completed.stdout)
        self.assertIn("Real downstream accepted: `False`", completed.stdout)
        self.assertIn("结构化制片包可交接", completed.stdout)
        self.assertIn("资产身份证和引用链路完整", completed.stdout)
        self.assertIn("人物和道具基础资产保持干净背景", completed.stdout)
        self.assertIn("提示词具备导演执行信息", completed.stdout)
        self.assertIn("真实画质声明边界清楚", completed.stdout)


if __name__ == "__main__":
    unittest.main()
