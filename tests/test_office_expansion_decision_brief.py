import json
import subprocess
import sys
import unittest
from pathlib import Path


class OfficeExpansionDecisionBriefTests(unittest.TestCase):
    def test_decision_brief_is_bound_to_research_and_future_office_evidence(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_office_expansion_decision_brief.py",
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
        self.assertEqual(payload["mode"], "office_expansion_decision_brief")
        self.assertEqual(payload["document"], "docs/OFFICE_EXPANSION_DECISION_BRIEF.md")
        self.assertEqual(payload["missing_marker_count"], 0)
        self.assertEqual(payload["research_claim_level"], "staged_research_demo")
        self.assertFalse(payload["research_full_automation"])
        self.assertEqual(
            payload["future_priority_order"],
            ["ecommerce_selection", "short_video_ads", "story_ip", "technical_project"],
        )
        self.assertEqual(payload["future_prioritization_status"], "decision_ready_but_not_started")
        self.assertEqual(payload["future_blocked_candidates"], "4/4")
        self.assertIn("future_schema_validators", payload["future_backlog_ids"])
        self.assertIn("future_recovery_events", payload["future_backlog_ids"])

    def test_decision_brief_explains_why_ecommerce_selection_is_first(self):
        text = Path("docs/OFFICE_EXPANSION_DECISION_BRIEF.md").read_text(encoding="utf-8")

        self.assertIn("用户真正需要的不是更多按钮，而是交付确定性", text)
        self.assertIn("优先候选。它最能复用研究办公室的数据、竞品、截图计划和 staged claim 边界", text)
        self.assertIn("不能进入公开主入口", text)
        self.assertIn("不能宣称已经做到全自动飞瓜会员级采集", text)

    def test_markdown_output_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_office_expansion_decision_brief.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Office Expansion Decision Brief Audit", completed.stdout)
        self.assertIn("Research claim: staged_research_demo / full automation=False", completed.stdout)
        self.assertIn("Future priority order: ecommerce_selection, short_video_ads, story_ip, technical_project", completed.stdout)


if __name__ == "__main__":
    unittest.main()

