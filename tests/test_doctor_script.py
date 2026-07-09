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
        self.assertIn("办公室可用性", result.stdout)
        self.assertIn("Office launch gates", result.stdout)
        self.assertIn("AI 漫剧制片办公室能力", result.stdout)
        self.assertIn("下一步", result.stdout)
        self.assertNotIn("api_key", result.stdout.lower())
        self.assertNotIn("LiteLLM", result.stdout + result.stderr)

    def test_doctor_markdown_tables_have_consistent_columns(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        lines = result.stdout.splitlines()
        for index, line in enumerate(lines):
            if not (line.startswith("| ") and index + 1 < len(lines) and lines[index + 1].startswith("| ---")):
                continue
            expected_columns = line.count("|") - 1
            row_index = index + 2
            while row_index < len(lines) and lines[row_index].startswith("| "):
                actual_columns = lines[row_index].count("|") - 1
                self.assertEqual(
                    expected_columns,
                    actual_columns,
                    f"Markdown table row has {actual_columns} columns, expected {expected_columns}: {lines[row_index]}",
                )
                row_index += 1

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
        self.assertIn("offices", payload)
        self.assertEqual(payload["office"]["office_id"], "comic_production")
        office_ids = {office["office_id"] for office in payload["offices"]}
        self.assertIn("research", office_ids)
        self.assertIn("comic_production", office_ids)
        self.assertTrue(all("summary" in office for office in payload["offices"]))
        self.assertTrue(all("next_action" in office for office in payload["offices"]))
        self.assertTrue(all("launch_gate_status" in office for office in payload["offices"]))
        self.assertTrue(all("launch_gate_passed" in office for office in payload["offices"]))
        self.assertTrue(all("launch_gate_total" in office for office in payload["offices"]))
        self.assertNotIn("api_key", result.stdout.lower())
        self.assertNotIn("LiteLLM", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
