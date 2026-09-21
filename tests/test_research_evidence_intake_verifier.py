import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.verify_research_evidence_intake import verify_research_evidence_intake


class ResearchEvidenceIntakeVerifierTests(unittest.TestCase):
    def test_default_template_passes_offline_intake_audit(self):
        payload = verify_research_evidence_intake()

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "research_evidence_intake")
        self.assertEqual(payload["source_count"], 1)
        self.assertEqual(payload["screenshot_count"], 1)
        self.assertEqual(payload["data_row_count"], 1)
        self.assertEqual(payload["claim_count"], 1)
        self.assertEqual(payload["gap_card_count"], 1)
        self.assertTrue(payload["operator_staged_approved"])
        self.assertFalse(payload["operator_final_approved"])
        self.assertFalse(payload["summary_ready_for_final"])
        self.assertFalse(payload["errors"])

    def test_markdown_output_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_research_evidence_intake.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Research Evidence Intake Audit", completed.stdout)
        self.assertIn("Status: `passed`", completed.stdout)
        self.assertIn("Sources: 1", completed.stdout)
        self.assertIn("Screenshots: 1", completed.stdout)
        self.assertIn("Evidence gaps: 1", completed.stdout)
        self.assertIn("Final approved: False", completed.stdout)

    def test_rejects_broken_references_and_private_account_data(self):
        template = json.loads(Path("docs/RESEARCH_EVIDENCE_INTAKE_TEMPLATE.json").read_text(encoding="utf-8"))
        template["screenshot_records"][0]["claim_ids"] = ["missing_claim"]
        template["screenshot_records"][0]["contains_private_account_data"] = True
        template["research_evidence_summary"]["screenshot_count"] = 99

        with tempfile.TemporaryDirectory() as temp_dir:
            intake_path = Path(temp_dir) / "bad_research_intake.json"
            intake_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
            payload = verify_research_evidence_intake(intake_path)

        self.assertEqual(payload["status"], "failed")
        errors = "\n".join(payload["errors"])
        self.assertIn("references unknown claim_id: missing_claim", errors)
        self.assertIn("must remove private account data", errors)
        self.assertIn("research_evidence_summary.screenshot_count expected 1, got 99", errors)


if __name__ == "__main__":
    unittest.main()
