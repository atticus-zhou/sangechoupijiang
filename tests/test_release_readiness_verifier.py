import json
import subprocess
import sys
import unittest


class ReleaseReadinessVerifierTests(unittest.TestCase):
    def test_json_runs_all_public_release_gates(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_release_readiness.py",
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
        self.assertTrue(payload["safe_for_public_release"])
        self.assertFalse(payload["failures"])

        check_ids = {item["id"] for item in payload["checks"]}
        self.assertEqual(
            check_ids,
            {
                "first_run",
                "productization_status",
                "model_guidance",
                "public_demo",
                "comic_delivery",
                "comic_downstream_handoff",
                "research_readiness",
                "office_governance",
                "product_readiness",
                "secret_scan",
            },
        )
        for check in payload["checks"]:
            self.assertEqual(check["status"], "passed")
            self.assertTrue(check["summary"])
            self.assertTrue(check["command"].startswith("python scripts/"))
        self.assertNotIn("sk-", completed.stdout.lower())

    def test_markdown_is_release_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_release_readiness.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Release Readiness Audit", completed.stdout)
        self.assertIn("Safe for public release", completed.stdout)
        self.assertIn("Productization objective coverage", completed.stdout)
        self.assertIn("Model configuration guidance", completed.stdout)
        self.assertIn("AI comic Word canvas delivery", completed.stdout)
        self.assertIn("AI comic downstream handoff", completed.stdout)
        self.assertIn("Research office staged delivery", completed.stdout)
        self.assertIn("Secret and runtime artifact scan", completed.stdout)


if __name__ == "__main__":
    unittest.main()
