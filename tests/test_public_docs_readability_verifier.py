import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.verify_public_docs_readability import _find_suspicious_markers


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
        self.assertIn("START_HERE.md", checked_paths)
        self.assertIn("README.md", checked_paths)
        self.assertIn("docs/DEPLOYMENT_MODES.md", checked_paths)
        self.assertIn("docs/PUBLIC_RELEASE_HANDOFF.md", checked_paths)
        self.assertIn("docs/COMIC_DOWNSTREAM_HANDOFF.md", checked_paths)
        self.assertIn("docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md", checked_paths)
        self.assertIn("docs/NEW_OFFICE_STARTER_CHECKLIST.md", checked_paths)
        self.assertIn("docs/OFFICE_EXPANSION_DECISION_BRIEF.md", checked_paths)
        self.assertIn("docs/FIRST_RUN_DECISION_CARD.md", checked_paths)
        static_doc = next(item for item in payload["docs"] if item["path"] == "docs/STATIC_SHOWCASE_DEPLOYMENT.md")
        self.assertFalse(static_doc["missing_markers"])
        for item in payload["docs"]:
            self.assertEqual(item["status"], "passed")
            self.assertFalse(item["read_error"])
            self.assertFalse(item["suspicious_markers"])
            self.assertFalse(item["missing_markers"])

    def test_public_status_doc_is_not_left_in_legacy_cleanup_state(self):
        text = Path("docs/PRODUCTIZATION_STATUS.md").read_text(encoding="utf-8")

        self.assertNotIn("历史状态表和旧门禁标记", text)
        self.assertEqual(text.count("## 一键总门禁"), 1)

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
        self.assertIn("START_HERE.md", completed.stdout)
        self.assertIn("short GitHub first-run entry", completed.stdout)
        self.assertIn("README.md", completed.stdout)
        self.assertIn("GitHub front door", completed.stdout)
        self.assertIn("deployment boundary", completed.stdout)
        self.assertIn("comic downstream handoff", completed.stdout)
        self.assertIn("comic real-run evidence intake", completed.stdout)
        self.assertIn("docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md", completed.stdout)
        self.assertIn("new office starter checklist", completed.stdout)
        self.assertIn("office expansion decision brief", completed.stdout)
        self.assertIn("first-run decision card", completed.stdout)
        self.assertIn("docs/FIRST_RUN_DECISION_CARD.md", completed.stdout)
        self.assertIn("docs/NEW_OFFICE_STARTER_CHECKLIST.md", completed.stdout)
        self.assertIn("docs/OFFICE_EXPANSION_DECISION_BRIEF.md", completed.stdout)
        self.assertIn("Docs: `", completed.stdout)

    def test_suspicious_marker_detector_catches_mojibake_without_flagging_clean_chinese(self):
        clean = "三个臭皮匠是本地优先的多 Agent 协作工作台。"
        corrupted = "\u6d93\u5909\u91dc\u9477\ue160\u6bca\u9366\u72b3\u69f8\u93c8\ue100\u6e74\u6d7c\u6a3a\u539b\u9428\u52eb\ue63f Agent workspace"

        self.assertEqual(_find_suspicious_markers(clean), [])
        suspicious = _find_suspicious_markers(corrupted)
        self.assertIn("\u6d93\u5909\u91dc", suspicious)
        self.assertIn("\u9477", suspicious)


if __name__ == "__main__":
    unittest.main()
