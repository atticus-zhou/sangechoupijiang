import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_public_demo_mode.py")


class PublicDemoVerifierTests(unittest.TestCase):
    def test_json_verifies_no_key_demo_endpoints_and_downloads(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "public_no_key_demo")
        self.assertEqual(payload["showcase_manifest"]["status_code"], 200)
        self.assertEqual(payload["showcase_manifest"]["mode"], "public_no_key_showcase")
        self.assertGreaterEqual(payload["showcase_manifest"]["audience_path_count"], 3)
        self.assertGreaterEqual(payload["showcase_manifest"]["featured_demo_count"], 2)
        self.assertGreaterEqual(payload["showcase_manifest"]["reading_guide_count"], 4)
        self.assertEqual(
            payload["showcase_manifest"]["reading_guide_count"],
            payload["showcase_manifest"]["reading_guide_ready_count"],
        )
        self.assertIn("comic_production", payload["demos"])
        self.assertIn("research", payload["demos"])
        for demo in payload["demos"].values():
            self.assertTrue(demo["available"] )
            self.assertFalse(demo["requires_api_key"] )
            self.assertFalse(demo["calls_real_models"] )
            self.assertTrue(demo["read_only"] )
            self.assertGreaterEqual(len(demo["downloads"]), 2)
            for item in demo["downloads"]:
                self.assertEqual(item["status_code"], 200)
                self.assertGreater(item["bytes"], 20)
                self.assertTrue(item["uri"].startswith("/api/demo/"))

        links = "\n".join(payload["launch_gate_links"])
        self.assertIn("/api/demo/comic-production/files/word_canvas.docx", links)
        self.assertIn("/api/demo/comic-production/files/handoff_manifest.json", links)
        self.assertIn("/api/demo/research/files/report.md", links)
        self.assertIn("/api/demo/research/files/evidence_manifest.json", links)
        self.assertNotIn("sk-", result.stdout.lower())

    def test_markdown_is_readable_for_public_showcase(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("公开演示模式验证", result.stdout)
        self.assertIn("AI 漫剧制片办公室", result.stdout)
        self.assertIn("研究办公室", result.stdout)
        self.assertIn("下载链接", result.stdout)
        self.assertIn("公开展示清单", result.stdout)
        self.assertIn("交付物阅读顺序", result.stdout)
        self.assertIn("不调用真实模型", result.stdout)


if __name__ == "__main__":
    unittest.main()

