import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.verify_research_evidence_intake import verify_research_evidence_intake


def _fill_research_placeholders(payload):
    if isinstance(payload, dict):
        return {key: _fill_research_placeholders(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_fill_research_placeholders(value) for value in payload]
    if isinstance(payload, str):
        replacements = {
            "ws_replace_with_real_workspace_id": "ws_research_real_001",
            "task_replace_with_real_task_id": "task_research_real_001",
            "replace_with_research_object": "民用无人机",
            "research_report_v_replace": "research_report_v1",
            "research_evidence_manifest_v_replace": "research_evidence_manifest_v1",
            "replace_source_title": "飞瓜民用无人机商品榜单",
            "https://example.com/replace": "https://example.com/feigua-drone-rank",
            "replace_metric_name": "榜单样本价",
            "replace_metric_value": "2999-6999",
            "replace_unit": "元",
            "replace_time_range": "2026-W38",
            "replace_research_claim": "民用无人机样本价格集中在中高价位",
            "replace_report_section": "价格带分析",
            "replace_missing_evidence": "补一张商品详情页截图用于确认 SKU 参数",
            "2026-01-01T00:00:00Z": "2026-09-21T12:00:00Z",
        }
        for old, new in replacements.items():
            payload = payload.replace(old, new)
        return payload
    return payload


class ResearchEvidenceIntakeVerifierTests(unittest.TestCase):
    def test_default_template_passes_offline_intake_audit(self):
        payload = verify_research_evidence_intake()

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "research_evidence_intake")
        self.assertEqual(payload["source_count"], 1)
        self.assertEqual(payload["screenshot_count"], 1)
        self.assertEqual(payload["data_row_count"], 1)
        self.assertEqual(payload["claim_count"], 1)
        self.assertEqual(payload["gap_card_count"], 1)
        self.assertTrue(payload["operator_staged_approved"])
        self.assertFalse(payload["operator_final_approved"])
        self.assertFalse(payload["summary_ready_for_final"])
        self.assertFalse(payload["errors"])

    def test_markdown_output_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_research_evidence_intake.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Research Evidence Intake Audit", completed.stdout)
        self.assertIn("Status: `passed`", completed.stdout)
        self.assertIn("Sources: 1", completed.stdout)
        self.assertIn("Screenshots: 1", completed.stdout)
        self.assertIn("Evidence gaps: 1", completed.stdout)
        self.assertIn("Final approved: False", completed.stdout)

    def test_rejects_broken_references_and_private_account_data(self):
        template = json.loads(Path("docs/RESEARCH_EVIDENCE_INTAKE_TEMPLATE.json").read_text(encoding="utf-8"))
        template["screenshot_records"][0]["claim_ids"] = ["missing_claim"]
        template["screenshot_records"][0]["contains_private_account_data"] = True
        template["research_evidence_summary"]["screenshot_count"] = 99

        with tempfile.TemporaryDirectory() as temp_dir:
            intake_path = Path(temp_dir) / "bad_research_intake.json"
            intake_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
            payload = verify_research_evidence_intake(intake_path)

        self.assertEqual(payload["status"], "failed")
        errors = "\n".join(payload["errors"])
        self.assertIn("references unknown claim_id: missing_claim", errors)
        self.assertIn("must remove private account data", errors)
        self.assertIn("research_evidence_summary.screenshot_count expected 1, got 99", errors)

    def test_strict_real_values_rejects_unfilled_template_placeholders(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_research_evidence_intake.py",
                "--strict-real-values",
                "--format",
                "markdown",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Strict real values: `True`", completed.stdout)
        self.assertIn("placeholder values", completed.stdout)
        self.assertIn("$.workspace.workspace_id", completed.stdout)

    def test_strict_real_values_accepts_filled_research_evidence_file(self):
        template = json.loads(Path("docs/RESEARCH_EVIDENCE_INTAKE_TEMPLATE.json").read_text(encoding="utf-8"))
        template = _fill_research_placeholders(template)

        with tempfile.TemporaryDirectory() as temp_dir:
            intake_path = Path(temp_dir) / "research_evidence_real.json"
            intake_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
            payload = verify_research_evidence_intake(intake_path, strict_real_values=True)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["strict_real_values"])
        self.assertEqual(payload["source_count"], 1)
        self.assertEqual(payload["screenshot_count"], 1)
        self.assertFalse(payload["summary_ready_for_final"])
        self.assertFalse(payload["errors"])


if __name__ == "__main__":
    unittest.main()
