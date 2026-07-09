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
        self.assertTrue(paths["local_real_use"]["requires_api_key"])
        self.assertIn("config.yaml", "\n".join(paths["local_real_use"]["steps"]))
        self.assertIn("verify_office_isolation.py", "\n".join(paths["developer_extension"]["steps"]))

        safety = "\n".join(payload["safety_boundaries"])
        self.assertIn("API Key", safety)
        self.assertIn("user_data", safety)
        self.assertIn("output", safety)

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
        self.assertIn("python scripts/verify_office_isolation.py --format markdown", result.stdout)


if __name__ == "__main__":
    unittest.main()
