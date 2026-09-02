import json
import subprocess
import sys
import unittest
from pathlib import Path


class ComicRealRunEvidenceIntakeTests(unittest.TestCase):
    def test_real_run_intake_is_bound_to_current_claim_gates(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_real_run_evidence_intake.py",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "comic_real_run_evidence_intake")
        self.assertEqual(payload["document"], "docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md")
        self.assertEqual(payload["missing_marker_count"], 0)
        self.assertEqual(payload["human_flow_step_count"], 6)
        self.assertEqual(payload["recovery_action_count"], 4)
        self.assertEqual(payload["benchmark_claim"], "demo_structure_verified")
        self.assertFalse(payload["benchmark_real_quality_verified"])
        self.assertEqual(payload["claim_level"], "demo_structure_only")
        self.assertFalse(payload["can_claim_real_quality"])
        self.assertEqual(payload["downstream_status"], "structure_demo_only")
        self.assertFalse(payload["handoff_allowed"])
        self.assertTrue(all(payload["section_status"].values()))

    def test_real_run_intake_explains_assets_prompts_word_and_recovery(self):
        text = Path("docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md").read_text(encoding="utf-8")

        self.assertIn("人物资产和道具资产默认应该是干净白底或极简背景", text)
        self.assertIn("不讲故事、不加剧情动作", text)
        self.assertIn("提示词不能只是固定模板堆词", text)
        self.assertIn("像导演交代现场一样", text)
        self.assertIn("哪张图服务哪个镜头，哪个镜头使用哪些资产", text)
        self.assertIn("不能让用户重新开盲盒", text)

    def test_markdown_output_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_real_run_evidence_intake.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("AI Comic Real-Run Evidence Intake Audit", completed.stdout)
        self.assertIn("Benchmark: `demo_structure_verified` / real_quality=False", completed.stdout)
        self.assertIn("Public claim: `demo_structure_only` / can_claim_real_quality=False", completed.stdout)
        self.assertIn("Downstream: `structure_demo_only` / handoff_allowed=False", completed.stdout)


if __name__ == "__main__":
    unittest.main()
