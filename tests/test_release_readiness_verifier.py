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
                "static_showcase",
                "comic_delivery",
                "comic_downstream_handoff",
                "comic_production_benchmark",
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
        public_demo = next(item for item in payload["checks"] if item["id"] == "public_demo")
        self.assertIn("reading_guide=", public_demo["summary"])
        self.assertIn("interview_script=", public_demo["summary"])
        static_showcase = next(item for item in payload["checks"] if item["id"] == "static_showcase")
        self.assertIn("downloads=4", static_showcase["summary"])
        self.assertIn("backend=False", static_showcase["summary"])
        comic_handoff = next(item for item in payload["checks"] if item["id"] == "comic_downstream_handoff")
        self.assertIn("structured_director_shots=2", comic_handoff["summary"])
        comic_benchmark = next(item for item in payload["checks"] if item["id"] == "comic_production_benchmark")
        self.assertIn("score=100", comic_benchmark["summary"])
        self.assertIn("claim=demo_structure_verified", comic_benchmark["summary"])
        self.assertIn("real_quality_verified=False", comic_benchmark["summary"])
        research_readiness = next(item for item in payload["checks"] if item["id"] == "research_readiness")
        self.assertIn("reading_guide=2/2", research_readiness["summary"])
        office_governance = next(item for item in payload["checks"] if item["id"] == "office_governance")
        self.assertIn("demo_contract=", office_governance["summary"])
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
        self.assertIn("Backend-free static showcase export", completed.stdout)
        self.assertIn("AI comic Word canvas delivery", completed.stdout)
        self.assertIn("AI comic downstream handoff", completed.stdout)
        self.assertIn("AI comic production quality benchmark", completed.stdout)
        self.assertIn("Research office staged delivery", completed.stdout)
        self.assertIn("Secret and runtime artifact scan", completed.stdout)
        self.assertIn("interview_script=4/4", completed.stdout)
        self.assertIn("downloads=4; reading_guide=4/4; backend=False", completed.stdout)
        self.assertIn("structured_director_shots=2", completed.stdout)
        self.assertIn("claim=demo_structure_verified", completed.stdout)
        self.assertIn("reading_guide=2/2", completed.stdout)
        self.assertIn("demo_contract=6", completed.stdout)


if __name__ == "__main__":
    unittest.main()
