from pathlib import Path
import unittest


class GitHubActionsReleaseReadinessTests(unittest.TestCase):
    def test_no_key_release_gate_workflow_exists(self):
        workflow = Path(".github/workflows/release-readiness.yml")
        self.assertTrue(workflow.is_file())

        text = workflow.read_text(encoding="utf-8")
        self.assertIn("Release readiness", text)
        self.assertIn("python -m pip install -r requirements.txt", text)
        self.assertIn("python scripts/verify_release_readiness.py --format markdown", text)
        self.assertIn("python scripts/check_no_secrets.py", text)
        self.assertIn("permissions:", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertNotIn("DASHSCOPE_API_KEY", text)
        self.assertNotIn("DEEPSEEK_API_KEY", text)
        self.assertNotIn("config.yaml", text)


if __name__ == "__main__":
    unittest.main()
