import json
import subprocess
import sys
import unittest


class ResearchOfficeReadinessVerifierTests(unittest.TestCase):
    def test_json_verifies_traceable_research_package_and_demo_downloads(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_research_office_readiness.py",
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

        package = payload["artifact_package"]
        self.assertEqual(package["quality"]["status"], "ready")
        self.assertEqual(package["quality"]["score"], 100)
        self.assertFalse(package["quality"]["warnings"])
        self.assertFalse(package["missing_artifacts"])
        self.assertTrue(package["has_screenshot_plan"])
        self.assertTrue(package["has_evidence_gap_cards"])
        self.assertTrue(package["has_source_trace"])
        self.assertTrue(package["has_data_table"])
        self.assertTrue(package["has_competitor_table"])

        for gate in package["schema_gates"].values():
            self.assertEqual(gate["status"], "passed")

        demo = payload["demo_endpoint"]
        self.assertEqual(demo["status"], "passed")
        self.assertEqual(demo["mode"], "no_key_demo")
        self.assertFalse(demo["requires_api_key"])
        self.assertFalse(demo["calls_real_models"])
        self.assertGreaterEqual(demo["download_count"], 2)
        self.assertGreaterEqual(demo["evidence_boundary_count"], 4)
        self.assertGreaterEqual(demo["human_or_account_boundary_count"], 3)
        self.assertIn("不宣称全自动", demo["public_demo_boundary"])
        self.assertGreaterEqual(demo["reading_guide_count"], 2)
        self.assertEqual(demo["reading_guide_count"], demo["reading_guide_ready_count"])
        self.assertGreaterEqual(demo["evidence_handoff_count"], 3)
        self.assertEqual(demo["evidence_handoff_count"], demo["evidence_handoff_ready_count"])
        self.assertGreaterEqual(demo["evidence_gap_card_count"], 3)
        self.assertEqual(demo["evidence_gap_card_count"], demo["evidence_gap_card_ready_count"])
        self.assertEqual(demo["capture_playbook_status"], "human_account_required")
        self.assertGreaterEqual(demo["capture_playbook_step_count"], 5)
        self.assertEqual(demo["capture_playbook_step_count"], demo["capture_playbook_ready_count"])
        self.assertGreaterEqual(demo["capture_playbook_command_count"], 3)
        self.assertEqual(demo["claim_report_status_code"], 200)
        self.assertEqual(demo["claim_level"], "staged_research_demo")
        self.assertFalse(demo["can_claim_full_automation"])
        self.assertGreaterEqual(demo["claim_upgrade_checklist_count"], 3)
        self.assertEqual(demo["evidence_claim_readiness"], "staged_only")
        self.assertFalse(demo["evidence_can_claim_final_report"])
        self.assertEqual(demo["research_evidence_requirements_status"], "staged_only")
        self.assertFalse(demo["research_ready_for_final_claim"])
        self.assertIn("pending_evidence_disclosed", demo["research_evidence_blocking_checks"])
        self.assertIn("placeholder_sources_disclosed", demo["research_evidence_blocking_checks"])
        self.assertIn("final_report_not_claimed", demo["research_evidence_blocking_checks"])
        self.assertGreaterEqual(demo["placeholder_demo_source_count"], 1)
        self.assertGreaterEqual(demo["pending_evidence_count"], 1)

    def test_markdown_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_research_office_readiness.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Research Office Readiness Audit", completed.stdout)
        self.assertIn("Artifact Package", completed.stdout)
        self.assertIn("Schema Gates", completed.stdout)
        self.assertIn("Public Demo", completed.stdout)
        self.assertIn("Evidence boundaries", completed.stdout)
        self.assertIn("Reading guide", completed.stdout)
        self.assertIn("Evidence handoff", completed.stdout)
        self.assertIn("Evidence capture playbook", completed.stdout)
        self.assertIn("human_account_required", completed.stdout)
        self.assertIn("Evidence claim readiness", completed.stdout)
        self.assertIn("Research evidence requirements", completed.stdout)
        self.assertIn("staged_only", completed.stdout)
        self.assertIn("Evidence status counts", completed.stdout)
        self.assertIn("Claim report", completed.stdout)
        self.assertIn("staged_research_demo", completed.stdout)
        self.assertIn("/api/demo/research/files/report.md", completed.stdout)


if __name__ == "__main__":
    unittest.main()
