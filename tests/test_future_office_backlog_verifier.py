import json
import os
import subprocess
import sys
import unittest


class FutureOfficeBacklogVerifierTests(unittest.TestCase):
    def test_json_keeps_future_offices_honestly_blocked(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_future_office_backlog.py",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "future_office_backlog")
        self.assertEqual(payload["candidate_count"], 4)
        self.assertEqual(payload["blocked_candidate_count"], 4)
        self.assertEqual(
            set(payload["candidate_ids"]),
            {"short_video_ads", "ecommerce_selection", "story_ip", "technical_project"},
        )
        self.assertEqual(
            set(payload["backlog_ids"]),
            {"future_schema_validators", "future_recovery_events"},
        )
        self.assertEqual(
            payload["priority_order"],
            ["ecommerce_selection", "short_video_ads", "story_ip", "technical_project"],
        )
        self.assertEqual(payload["prioritization_status"], "decision_ready_but_not_started")
        self.assertIn("复用现有证据链", payload["decision_rule"])
        self.assertGreaterEqual(len(payload["do_not_start_until"]), 3)
        self.assertEqual(payload["errors"], [])
        for report in payload["reports"]:
            self.assertEqual(report["status"], "blocked_until_evidence")
            self.assertIsInstance(report["priority_rank"], int)
            self.assertTrue(report["priority_label"])
            self.assertTrue(report["product_rationale"])
            self.assertTrue(report["defer_until"])
            self.assertIn("sample_delivery", report["required_before_public"])
            self.assertIn("schema_gate", report["required_before_public"])
            self.assertIn("public_claim_report", report["required_before_public"])
            self.assertIn("future_schema_validators", report["blocking_backlog_ids"])
            self.assertIn("future_recovery_events", report["blocking_backlog_ids"])

    def test_markdown_lists_each_candidate_and_platform_blocker(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_future_office_backlog.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        self.assertIn("Future Office Backlog", completed.stdout)
        self.assertIn("Status: `passed`", completed.stdout)
        self.assertIn("Candidates: 4/4 blocked until evidence", completed.stdout)
        self.assertIn("Priority order: ecommerce_selection, short_video_ads, story_ip, technical_project", completed.stdout)
        self.assertIn("decision_ready_but_not_started", completed.stdout)
        self.assertIn("short_video_ads", completed.stdout)
        self.assertIn("ecommerce_selection", completed.stdout)
        self.assertIn("story_ip", completed.stdout)
        self.assertIn("technical_project", completed.stdout)
        self.assertIn("future_schema_validators", completed.stdout)
        self.assertIn("future_recovery_events", completed.stdout)


if __name__ == "__main__":
    unittest.main()
