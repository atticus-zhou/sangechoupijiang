import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_office_isolation.py")


class OfficeIsolationVerifierTests(unittest.TestCase):
    def test_json_proves_models_workspaces_artifacts_and_history_are_office_scoped(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "offline_isolation_audit")
        self.assertEqual(payload["offices"], ["research", "comic_production"])
        self.assertTrue(payload["safe_for_public_repo"])
        self.assertNotIn("sk-", result.stdout.lower())

        checks = {item["id"]: item for item in payload["checks"]}
        for check_id in [
            "model_config_isolation",
            "workspace_scope_isolation",
            "artifact_scope_isolation",
            "history_trace_isolation",
            "filesystem_output_isolation",
        ]:
            self.assertIn(check_id, checks)
            self.assertEqual(checks[check_id]["status"], "passed")
            self.assertTrue(checks[check_id]["evidence"])

        self.assertIn("comic-qwen-vl", "\n".join(checks["model_config_isolation"]["evidence"]))
        self.assertIn("research-deepseek", "\n".join(checks["model_config_isolation"]["evidence"]))
        self.assertIn("workspace_id", "\n".join(checks["history_trace_isolation"]["evidence"]))

    def test_markdown_is_human_readable_for_release_checks(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Office Isolation Audit", result.stdout)
        self.assertIn("model_config_isolation", result.stdout)
        self.assertIn("workspace_scope_isolation", result.stdout)
        self.assertIn("artifact_scope_isolation", result.stdout)
        self.assertIn("history_trace_isolation", result.stdout)
        self.assertIn("filesystem_output_isolation", result.stdout)


if __name__ == "__main__":
    unittest.main()
