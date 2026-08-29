import json
import subprocess
import sys
import unittest


class PublicComicTraceBundleVerifierTests(unittest.TestCase):
    def test_json_verifier_checks_trace_contract(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_public_comic_trace_bundle.py",
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
        self.assertEqual(payload["mode"], "public_comic_trace_bundle")
        self.assertEqual(payload["uri"], "/api/demo/comic-production/files/trace.json")
        self.assertFalse(payload["requires_api_key"])
        self.assertFalse(payload["calls_real_models"])
        self.assertFalse(payload["writes_workspace"])
        self.assertEqual(payload["asset_count"], 3)
        self.assertEqual(payload["image_count"], 7)
        self.assertEqual(payload["shot_count"], 2)
        self.assertEqual(payload["claim_level"], "demo_structure_only")
        self.assertEqual(payload["quality_status"], "demo_structure_verified")
        self.assertEqual(payload["visual_evidence_level"], "fixture_only")
        self.assertFalse(payload["production_quality_verified"])
        self.assertEqual(payload["image_evidence_level"], "fixture_only")
        self.assertFalse(payload["supports_real_quality_claim"])
        self.assertEqual(payload["asset_type_quality"]["character"]["total"], 2)
        self.assertEqual(payload["asset_type_quality"]["prop"]["total"], 2)
        self.assertEqual(payload["asset_type_quality"]["scene"]["total"], 3)
        self.assertEqual(payload["real_model_evidence_status"], "evidence_missing")
        self.assertFalse(payload["real_model_evidence_ready"])
        self.assertIn("non_fixture_images", payload["real_model_evidence_missing_checks"])
        self.assertIn("provider_model_bound", payload["real_model_evidence_missing_checks"])
        self.assertNotIn("seven_dimension_scores", payload["real_model_evidence_missing_checks"])
        self.assertEqual(payload["downstream_handoff_status"], "structure_demo_only")
        self.assertFalse(payload["downstream_handoff_allowed"])
        self.assertGreaterEqual(payload["upgrade_checklist_count"], 3)
        self.assertGreaterEqual(payload["reproducibility_command_count"], 3)
        self.assertEqual(payload["errors"], [])
        self.assertNotIn("sk-", completed.stdout.lower())

    def test_markdown_is_public_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_public_comic_trace_bundle.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Public Comic Trace Bundle", completed.stdout)
        self.assertIn("Status: `passed`", completed.stdout)
        self.assertIn("Assets/images/shots: 3 / 7 / 2", completed.stdout)
        self.assertIn("Claim level: demo_structure_only", completed.stdout)
        self.assertIn("Image evidence: fixture_only / supports_real_quality=False", completed.stdout)
        self.assertIn("Asset type quality: character=2/2 passed, 0 rework", completed.stdout)
        self.assertIn("prop=2/2 passed, 0 rework", completed.stdout)
        self.assertIn("scene=3/3 passed, 0 rework", completed.stdout)
        self.assertIn("Real model evidence: evidence_missing / ready=False", completed.stdout)
        self.assertIn("Downstream handoff: structure_demo_only / allowed=False", completed.stdout)
        self.assertIn("non_fixture_images", completed.stdout)


if __name__ == "__main__":
    unittest.main()
