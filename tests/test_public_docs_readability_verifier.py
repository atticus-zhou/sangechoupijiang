import json
import subprocess
import sys
import unittest


class PublicDocsReadabilityVerifierTests(unittest.TestCase):
    def test_json_verifies_public_docs_are_readable_and_release_oriented(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_public_docs_readability.py",
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
        self.assertEqual(payload["mode"], "public_docs_readability")
        self.assertEqual(payload["failed_count"], 0)
        self.assertGreaterEqual(payload["doc_count"], 7)
        self.assertEqual(payload["passed_count"], payload["doc_count"])
        checked_paths = {item["path"] for item in payload["docs"]}
        self.assertIn("README.md", checked_paths)
        self.assertIn("docs/DEPLOYMENT_MODES.md", checked_paths)
        self.assertIn("docs/PUBLIC_RELEASE_HANDOFF.md", checked_paths)
        self.assertIn("docs/COMIC_DOWNSTREAM_HANDOFF.md", checked_paths)
        self.assertIn("docs/NEW_OFFICE_STARTER_CHECKLIST.md", checked_paths)
        for item in payload["docs"]:
            self.assertEqual(item["status"], "passed")
            self.assertFalse(item["read_error"])
            self.assertFalse(item["suspicious_markers"])
            self.assertFalse(item["missing_markers"])

    def test_markdown_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_public_docs_readability.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Public Docs Readability Audit", completed.stdout)
        self.assertIn("README.md", completed.stdout)
        self.assertIn("GitHub front door", completed.stdout)
        self.assertIn("deployment boundary", completed.stdout)
        self.assertIn("comic downstream handoff", completed.stdout)
        self.assertIn("new office starter checklist", completed.stdout)
        self.assertIn("docs/NEW_OFFICE_STARTER_CHECKLIST.md", completed.stdout)
        self.assertIn("Docs: `", completed.stdout)


if __name__ == "__main__":
    unittest.main()
