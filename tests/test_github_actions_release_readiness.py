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
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("no-key-release-evidence", text)
        self.assertIn("release-readiness-report/release-readiness.md", text)
        self.assertIn("release-readiness-report/secret-scan.txt", text)
        self.assertIn("permissions:", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertNotIn("DASHSCOPE_API_KEY", text)
        self.assertNotIn("DEEPSEEK_API_KEY", text)
        self.assertNotIn("config.yaml", text)

    def test_no_key_showcase_pages_workflow_exists(self):
        workflow = Path(".github/workflows/pages-showcase.yml")
        self.assertTrue(workflow.is_file())

        text = workflow.read_text(encoding="utf-8")
        self.assertIn("Public showcase pages", text)
        self.assertIn("workflow_dispatch", text)
        self.assertNotIn("push:", text)
        self.assertNotIn("branches:", text)
        self.assertIn("pages: write", text)
        self.assertIn("id-token: write", text)
        self.assertIn("python -m pip install -r requirements.txt", text)
        self.assertIn("python scripts/export_public_showcase.py --output dist/public-showcase --format json", text)
        self.assertIn("python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase", text)
        self.assertIn("python scripts/check_no_secrets.py", text)
        self.assertIn("Check GitHub Pages configuration", text)
        self.assertIn("GitHub Pages not enabled", text)
        self.assertIn("steps.pages_preflight.outputs.configured == 'true'", text)
        self.assertIn("Explain skipped Pages deployment", text)
        self.assertIn("actions/upload-pages-artifact@v3", text)
        self.assertIn("actions/deploy-pages@v4", text)
        self.assertIn("path: dist/public-showcase", text)
        self.assertIn("Verify published Pages URL", text)
        self.assertIn(
            "python scripts/verify_public_showcase_live.py --url https://atticus-zhou.github.io/sangechoupijiang/ --format markdown",
            text,
        )
        self.assertIn("GitHub Pages deployed and verified", text)
        self.assertIn("Enable Settings -> Pages -> Source: GitHub Actions", text)
        self.assertNotIn("continue-on-error: true", text)
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertNotIn("DASHSCOPE_API_KEY", text)
        self.assertNotIn("DEEPSEEK_API_KEY", text)
        self.assertNotIn("config.yaml", text)


if __name__ == "__main__":
    unittest.main()
