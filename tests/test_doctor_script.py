import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/doctor.py")


class DoctorScriptTests(unittest.TestCase):
    def test_doctor_outputs_user_facing_markdown(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("三个臭皮匠本地自检", result.stdout)
        self.assertIn("系统启动检查", result.stdout)
        self.assertIn("AI 漫剧制片办公室能力", result.stdout)
        self.assertIn("下一步", result.stdout)
        self.assertNotIn("api_key", result.stdout.lower())

    def test_doctor_outputs_json_without_secrets(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)

        self.assertIn(payload["status"], {"ready", "partial", "blocked"})
        self.assertIn("system", payload)
        self.assertIn("office", payload)
        self.assertEqual(payload["office"]["office_id"], "comic_production")
        self.assertNotIn("api_key", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
