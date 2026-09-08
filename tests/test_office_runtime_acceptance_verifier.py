import json
import subprocess
import sys
import unittest


class OfficeRuntimeAcceptanceVerifierTests(unittest.TestCase):
    def test_json_verifies_research_and_comic_acceptance_cards(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_office_runtime_acceptance.py",
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
        self.assertEqual(payload["mode"], "office_runtime_acceptance_contract")
        self.assertEqual(payload["offices"], ["comic_production", "research"])
        self.assertEqual(payload["acceptance_statuses"]["research"], "staged_report_ready")
        self.assertEqual(
            payload["acceptance_statuses"]["comic_production"],
            "structure_ready_needs_real_quality",
        )
        self.assertFalse(payload["errors"])

        research = payload["audit"]["research"]
        comic = payload["audit"]["comic_production"]
        self.assertEqual(research["status"], "passed")
        self.assertEqual(comic["status"], "passed")
        self.assertGreaterEqual(research["acceptance_item_count"], 5)
        self.assertGreaterEqual(comic["acceptance_item_count"], 5)
        self.assertIn("阶段可用", research["claim"])
        self.assertEqual(comic["claim"], "不可以")

        research_downloads = payload["download_labels"]["research"]
        comic_downloads = payload["download_labels"]["comic_production"]
        self.assertEqual(research_downloads["word_canvas_label"], "下载阶段报告")
        self.assertEqual(comic_downloads["word_canvas_label"], "下载 Word")
        self.assertEqual(comic_downloads["handoff_manifest_label"], "下载引用清单")

    def test_markdown_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_office_runtime_acceptance.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Office Runtime Acceptance Contract", completed.stdout)
        self.assertIn("research", completed.stdout)
        self.assertIn("comic_production", completed.stdout)
        self.assertIn("staged_report_ready", completed.stdout)
        self.assertIn("structure_ready_needs_real_quality", completed.stdout)
