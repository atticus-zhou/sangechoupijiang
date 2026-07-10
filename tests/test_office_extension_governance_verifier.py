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

        by_office = {item["office_id"]: item for item in audit["offices"]}
        self.assertTrue(by_office["comic_production"]["primary_allowed"])
        self.assertFalse(by_office["comic"]["can_be_primary"])

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
        self.assertIn("可展示", completed.stdout)
        self.assertIn("可试用", completed.stdout)
        self.assertIn("可交付", completed.stdout)
        self.assertIn("可追溯", completed.stdout)
        self.assertIn("comic_production", completed.stdout)


if __name__ == "__main__":
    unittest.main()
