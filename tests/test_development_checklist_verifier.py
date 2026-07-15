import json
import subprocess
import sys
import unittest


class DevelopmentChecklistVerifierTests(unittest.TestCase):
    def test_json_exposes_post_change_checks_without_running_heavy_gates(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_development_checklist.py",
                "--format",
                "json",
                "--skip-release",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "development_post_change_checklist")
        check_ids = {item["id"] for item in payload["checks"]}
        self.assertEqual(
            check_ids,
            {
                "git_status",
                "diff_check",
                "secret_scan",
                "office_isolation",
                "release_readiness",
                "unit_tests",
            },
        )
        release = next(item for item in payload["checks"] if item["id"] == "release_readiness")
        self.assertEqual(release["status"], "skipped")
        tests = next(item for item in payload["checks"] if item["id"] == "unit_tests")
        self.assertEqual(tests["status"], "skipped")
        self.assertIn("--run-tests", payload["next_action"])

    def test_markdown_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_development_checklist.py",
                "--format",
                "markdown",
                "--skip-release",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Development Checklist Audit", completed.stdout)
        self.assertIn("Git status", completed.stdout)
        self.assertIn("Whitespace diff check", completed.stdout)
        self.assertIn("Secret and runtime artifact scan", completed.stdout)
        self.assertIn("Office isolation", completed.stdout)
        self.assertIn("Release readiness", completed.stdout)
        self.assertIn("Full unit test suite", completed.stdout)
        self.assertIn("python -m unittest discover -s tests -q", completed.stdout)


if __name__ == "__main__":
    unittest.main()
