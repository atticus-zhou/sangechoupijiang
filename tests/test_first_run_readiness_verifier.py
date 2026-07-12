import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_first_run_readiness.py")


class FirstRunReadinessVerifierTests(unittest.TestCase):
    def test_json_guides_new_user_through_demo_local_and_developer_paths(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["status"], "ready_for_guided_first_run")
        self.assertEqual(payload["mode"], "new_user_reproducibility")
        self.assertTrue(payload["safe_for_public_repo"])
        self.assertNotIn("sk-", result.stdout.lower())

        paths = {item["id"]: item for item in payload["paths"]}
        for path_id in ["public_demo", "local_real_use", "developer_extension"]:
            self.assertIn(path_id, paths)
            self.assertIn(paths[path_id]["status"], {"ready", "needs_user_action"})
            self.assertGreaterEqual(len(paths[path_id]["steps"]), 3)
            self.assertTrue(paths[path_id]["next_action"])

        self.assertEqual(paths["public_demo"]["status"], "ready")
        self.assertFalse(paths["public_demo"]["requires_api_key"])
        self.assertIn("/api/demo/public-showcase", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("/api/demo/comic-production/files/handoff_manifest.json", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("/api/demo/research/files/evidence_manifest.json", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("verify_comic_v2_downstream_handoff.py", "\n".join(paths["public_demo"]["steps"]))
        self.assertIn("export_public_showcase.py", "\n".join(paths["public_demo"]["steps"]))
        self.assertIn("dist/public-showcase/index.html", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("docs/COMIC_DOWNSTREAM_HANDOFF.md", "\n".join(paths["public_demo"]["evidence"]))
        reading_guide = paths["public_demo"]["deliverable_reading_guide"]
        self.assertGreaterEqual(len(reading_guide), 4)
        self.assertTrue(all(item["file"] and item["uri"] and item["look_for"] and item["proves"] for item in reading_guide))
        self.assertTrue(any("Word 制片画布" in item["file"] for item in reading_guide))
        self.assertTrue(any("handoff manifest" in item["file"] for item in reading_guide))
        self.assertTrue(any("证据清单" in item["file"] for item in reading_guide))
        self.assertTrue(paths["local_real_use"]["requires_api_key"])
        self.assertIn("config.yaml", "\n".join(paths["local_real_use"]["steps"]))
        self.assertIn("verify_office_isolation.py", "\n".join(paths["developer_extension"]["steps"]))

        safety = "\n".join(payload["safety_boundaries"])
        self.assertIn("API Key", safety)
        self.assertIn("user_data", safety)
        self.assertIn("output", safety)

        failures = {item["id"]: item for item in payload["common_first_run_failures"]}
        for failure_id in [
            "missing_dependencies",
            "missing_local_config",
            "model_preflight_blocked",
            "port_in_use",
            "public_deploy_real_mode",
        ]:
            self.assertIn(failure_id, failures)
            self.assertTrue(failures[failure_id]["symptom"])
            self.assertTrue(failures[failure_id]["check_command"])
            self.assertTrue(failures[failure_id]["recovery_action"])
        self.assertFalse(failures["missing_dependencies"]["requires_api_key"])
        self.assertTrue(failures["model_preflight_blocked"]["requires_api_key"])
        self.assertIn("requirements.txt", failures["missing_dependencies"]["recovery_action"])
        self.assertIn("dist/public-showcase", failures["public_deploy_real_mode"]["recovery_action"])

    def test_markdown_is_readable_as_a_github_first_run_checklist(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("# First Run Readiness", result.stdout)
        self.assertIn("public_demo", result.stdout)
        self.assertIn("local_real_use", result.stdout)
        self.assertIn("developer_extension", result.stdout)
        self.assertIn("python run.py --port 8080", result.stdout)
        self.assertIn("python scripts/verify_public_demo_mode.py --format markdown", result.stdout)
        self.assertIn("python scripts/export_public_showcase.py", result.stdout)
        self.assertIn("python scripts/verify_static_public_showcase.py --format markdown", result.stdout)
        self.assertIn("python scripts/verify_comic_v2_downstream_handoff.py --format markdown", result.stdout)
        self.assertIn("python scripts/verify_office_isolation.py --format markdown", result.stdout)
        self.assertIn("Deliverable reading guide", result.stdout)
        self.assertIn("AI 漫剧 Word 制片画布", result.stdout)
        self.assertIn("handoff manifest", result.stdout)
        self.assertIn("研究办公室证据清单", result.stdout)
        self.assertIn("Common First-run Failures", result.stdout)
        self.assertIn("missing_dependencies", result.stdout)
        self.assertIn("python -m pip install -r requirements.txt", result.stdout)
        self.assertIn("netstat -ano | findstr :8080", result.stdout)
        self.assertIn("public_deploy_real_mode", result.stdout)


if __name__ == "__main__":
    unittest.main()
