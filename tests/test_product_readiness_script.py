import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_product_readiness.py")


class ProductReadinessScriptTests(unittest.TestCase):
    def test_script_outputs_json_readiness_audit(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["office_id"], "comic_production")
        self.assertEqual(payload["status"], "ready_without_demo")
        self.assertTrue(payload["checks"])

    def test_script_outputs_markdown_readiness_audit(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("AI 漫剧制片办公室真实产品 readiness", result.stdout)
        self.assertIn("完整工作流状态", result.stdout)


if __name__ == "__main__":
    unittest.main()
