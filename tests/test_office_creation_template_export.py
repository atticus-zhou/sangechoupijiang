import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.export_office_creation_template import export_office_creation_template, render_markdown


class OfficeCreationTemplateExportTests(unittest.TestCase):
    def test_export_payload_is_safe_and_actionable(self):
        payload = export_office_creation_template()

        self.assertEqual(payload["status"], "ready")
        self.assertFalse(payload["requires_api_key"])
        self.assertFalse(payload["calls_real_models"])
        self.assertFalse(payload["writes_workspace"])
        template = payload["template"]
        self.assertIn("office_profile_skeleton", template)
        self.assertIn("public_demo_contract_skeleton", template)
        profile = template["office_profile_skeleton"]
        self.assertIn("schema_gates", profile)
        self.assertIn("recovery_actions", profile)
        self.assertIn("preserves", profile["recovery_actions"][0])
        self.assertIn("clears", profile["recovery_actions"][0])
        self.assertIn("future_office_candidates", payload["blueprint"])
        self.assertTrue(payload["quick_start"])

    def test_markdown_is_human_readable(self):
        markdown = render_markdown(export_office_creation_template())

        self.assertIn("# 新办公室启动包", markdown)
        self.assertIn("OfficeProfile 必填字段", markdown)
        self.assertIn("上线门禁", markdown)
        self.assertIn("后续候选办公室", markdown)
        self.assertIn("verify_release_readiness.py", markdown)

    def test_cli_json_and_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "new_office_template.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/export_office_creation_template.py",
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            stdout_payload = json.loads(completed.stdout)
            file_payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(stdout_payload["mode"], "offline_new_office_creation_template")
            self.assertEqual(file_payload["template"]["office_profile_skeleton"]["id"], "new_office_id")


if __name__ == "__main__":
    unittest.main()
