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
        self.assertFalse(package["missing_artifacts"])
        self.assertTrue(package["has_screenshot_plan"])
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
        self.assertIn("/api/demo/research/files/report.md", completed.stdout)


if __name__ == "__main__":
    unittest.main()
