import json
import subprocess
import sys
import unittest


class OfficeExtensionGovernanceVerifierTests(unittest.TestCase):
    def test_json_proves_primary_office_can_be_promoted(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_office_extension_governance.py",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        audit = json.loads(completed.stdout)
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["primary_office_ids"], ["comic_production"])
        self.assertIn("required_demo_contract", audit)
        self.assertIn("extension_blueprint", audit)
        self.assertIn("protocol_doc", audit)
        self.assertEqual(audit["protocol_doc"]["status"], "passed")
        self.assertEqual(audit["protocol_doc"]["path"], "docs/OFFICE_EXTENSION_PROTOCOL.md")
        self.assertIn("deliverable_reading_guide", audit["required_demo_contract"])
        self.assertIn("interview_demo_script", audit["required_demo_contract"])
        self.assertIn("public_safety_boundaries", audit["required_demo_contract"])
        step_ids = {step["id"] for step in audit["extension_blueprint"]["implementation_steps"]}
        self.assertIn("register_profile", step_ids)
        self.assertIn("isolate_runtime", step_ids)
        self.assertIn("build_no_key_demo", step_ids)

        by_office = {item["office_id"]: item for item in audit["offices"]}
        self.assertTrue(by_office["comic_production"]["primary_allowed"])
        self.assertFalse(by_office["comic"]["can_be_primary"])
        self.assertEqual(by_office["comic"]["legacy_migration"]["target_office_id"], "comic_production")
        self.assertIn("comic_production", by_office["comic"]["legacy_migration"]["action"])

    def test_markdown_lists_four_primary_standards(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_office_extension_governance.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Office Extension Governance Audit", completed.stdout)
        self.assertIn("Required Demo Contract", completed.stdout)
        self.assertIn("Extension Blueprint", completed.stdout)
        self.assertIn("Register an OfficeProfile", completed.stdout)
        self.assertIn("Isolate runtime state", completed.stdout)
        self.assertIn("Build a no-key demo contract", completed.stdout)
        self.assertIn("verify_release_readiness.py", completed.stdout)
        self.assertIn("Human-Readable Protocol", completed.stdout)
        self.assertIn("OFFICE_EXTENSION_PROTOCOL.md", completed.stdout)
        self.assertIn("viewer_path", completed.stdout)
        self.assertIn("downloadable_deliverables", completed.stdout)
        self.assertIn("deliverable_reading_guide", completed.stdout)
        self.assertIn("interview_demo_script", completed.stdout)
        self.assertIn("public_safety_boundaries", completed.stdout)
        self.assertIn("可展示", completed.stdout)
        self.assertIn("可试用", completed.stdout)
        self.assertIn("可交付", completed.stdout)
        self.assertIn("可追溯", completed.stdout)
        self.assertIn("comic_production", completed.stdout)
        self.assertIn("Migration", completed.stdout)
        self.assertIn("旧 comic", completed.stdout)


if __name__ == "__main__":
    unittest.main()
