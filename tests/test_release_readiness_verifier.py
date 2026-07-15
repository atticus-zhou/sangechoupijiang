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
                "public_docs_readability",
                "public_demo",
                "static_showcase",
                "comic_delivery",
                "comic_downstream_handoff",
                "comic_production_benchmark",
                "comic_real_production_claim",
                "comic_handoff_inventory",
                "research_readiness",
                "office_governance",
                "office_isolation",
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
        self.assertIn("quick_start=5/5", public_demo["summary"])
        self.assertIn("interview_script=", public_demo["summary"])
        self.assertIn("reproducibility=5/5", public_demo["summary"])
        self.assertIn("badge=safe_public_demo", public_demo["summary"])
        static_showcase = next(item for item in payload["checks"] if item["id"] == "static_showcase")
        self.assertIn("downloads=5", static_showcase["summary"])
        self.assertIn("quick_start=5/5", static_showcase["summary"])
        self.assertIn("backend=False", static_showcase["summary"])
        public_docs = next(item for item in payload["checks"] if item["id"] == "public_docs_readability")
        self.assertIn("docs=", public_docs["summary"])
        self.assertIn("failures=0", public_docs["summary"])
        comic_delivery = next(item for item in payload["checks"] if item["id"] == "comic_delivery")
        self.assertIn("quick_start=5", comic_delivery["summary"])
        comic_handoff = next(item for item in payload["checks"] if item["id"] == "comic_downstream_handoff")
        self.assertIn("structured_director_shots=2", comic_handoff["summary"])
        self.assertIn("quick_start=5", comic_handoff["summary"])
        comic_benchmark = next(item for item in payload["checks"] if item["id"] == "comic_production_benchmark")
        self.assertIn("score=100", comic_benchmark["summary"])
        self.assertIn("claim=demo_structure_verified", comic_benchmark["summary"])
        self.assertIn("real_quality_verified=False", comic_benchmark["summary"])
        comic_claim = next(item for item in payload["checks"] if item["id"] == "comic_real_production_claim")
        self.assertIn("claim_level=demo_structure_only", comic_claim["summary"])
        self.assertIn("real_quality=False", comic_claim["summary"])
        self.assertIn("downstream=structure_demo_only", comic_claim["summary"])
        comic_inventory = next(item for item in payload["checks"] if item["id"] == "comic_handoff_inventory")
        self.assertIn("production_verified=0", comic_inventory["summary"])
        self.assertIn("demo_only=", comic_inventory["summary"])
        research_readiness = next(item for item in payload["checks"] if item["id"] == "research_readiness")
        self.assertIn("reading_guide=2/2", research_readiness["summary"])
        self.assertIn("handoff=3/3", research_readiness["summary"])
        office_governance = next(item for item in payload["checks"] if item["id"] == "office_governance")
        self.assertIn("demo_contract=", office_governance["summary"])
        office_isolation = next(item for item in payload["checks"] if item["id"] == "office_isolation")
        self.assertIn("checks=5", office_isolation["summary"])
        self.assertIn("failures=0", office_isolation["summary"])
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
        self.assertIn("Public docs readability", completed.stdout)
        self.assertIn("Backend-free static showcase export", completed.stdout)
        self.assertIn("AI comic Word canvas delivery", completed.stdout)
        self.assertIn("AI comic downstream handoff", completed.stdout)
        self.assertIn("AI comic production quality benchmark", completed.stdout)
        self.assertIn("AI comic real production claim boundary", completed.stdout)
        self.assertIn("AI comic handoff inventory", completed.stdout)
        self.assertIn("Research office staged delivery", completed.stdout)
        self.assertIn("Office isolation", completed.stdout)
        self.assertIn("Secret and runtime artifact scan", completed.stdout)
        self.assertIn("interview_script=4/4", completed.stdout)
        self.assertIn("reproducibility=5/5", completed.stdout)
        self.assertIn("quick_start=5/5", completed.stdout)
        self.assertIn("badge=safe_public_demo", completed.stdout)
        self.assertIn("downloads=5; reading_guide=5/5; quick_start=5/5; backend=False", completed.stdout)
        self.assertIn("failures=0; mode=public_docs_readability", completed.stdout)
        self.assertIn("structured_director_shots=2", completed.stdout)
        self.assertIn("quick_start=5", completed.stdout)
        self.assertIn("claim=demo_structure_verified", completed.stdout)
        self.assertIn("claim_level=demo_structure_only", completed.stdout)
        self.assertIn("production_verified=0", completed.stdout)
        self.assertIn("reading_guide=2/2", completed.stdout)
        self.assertIn("handoff=3/3", completed.stdout)
        self.assertIn("demo_contract=6", completed.stdout)
        self.assertIn("checks=5; failures=0", completed.stdout)


if __name__ == "__main__":
    unittest.main()
