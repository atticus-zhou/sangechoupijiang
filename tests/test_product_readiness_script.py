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
        self.assertEqual(payload["status"], "ready_with_demo")
        self.assertTrue(payload["checks"])
        no_key_demo = next(item for item in payload["checks"] if item["id"] == "no_key_demo")
        self.assertIn("research", "\n".join(no_key_demo["evidence"]))
        office_protocols = next(item for item in payload["checks"] if item["id"] == "office_protocols")
        self.assertEqual(office_protocols["status"], "passed")
        self.assertIn("src/offices.py", "\n".join(office_protocols["evidence"]))
        launch_gates = next(item for item in payload["checks"] if item["id"] == "office_launch_gate_audit")
        self.assertEqual(launch_gates["status"], "passed")
        self.assertIn("/api/offices/{office_id}/launch-gates", "\n".join(launch_gates["evidence"]))
        self.assertIn("office-launch-gates-panel", "\n".join(launch_gates["evidence"]))
        self.assertIn("evidence_links", "\n".join(launch_gates["evidence"]))
        self.assertIn("launch-gate-links", "\n".join(launch_gates["evidence"]))
        artifact_contract = next(item for item in payload["checks"] if item["id"] == "artifact_contract_runtime")
        self.assertEqual(artifact_contract["status"], "passed")
        self.assertIn("src/config_manager.py", "\n".join(artifact_contract["evidence"]))
        office_isolation = next(item for item in payload["checks"] if item["id"] == "office_isolation_contract")
        self.assertEqual(office_isolation["status"], "passed")
        self.assertIn("scripts/verify_office_isolation.py", "\n".join(office_isolation["evidence"]))
        self.assertIn("tests/test_office_isolation_verifier.py", "\n".join(office_isolation["evidence"]))
        first_run = next(item for item in payload["checks"] if item["id"] == "first_run_reproducibility")
        self.assertEqual(first_run["status"], "passed")
        self.assertIn("scripts/verify_first_run_readiness.py", "\n".join(first_run["evidence"]))
        self.assertIn("tests/test_first_run_readiness_verifier.py", "\n".join(first_run["evidence"]))
        schema_gate = next(item for item in payload["checks"] if item["id"] == "agent_output_schema_gate")
        self.assertEqual(schema_gate["status"], "passed")
        self.assertIn("src/comic_office/v2/output_schemas.py", "\n".join(schema_gate["evidence"]))
        self.assertIn("src/comic_office/v2/asset_planner.py", "\n".join(schema_gate["evidence"]))
        self.assertIn("src/comic_office/v2/production.py", "\n".join(schema_gate["evidence"]))

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
        self.assertIn("办公室协议", result.stdout)
        self.assertIn("产物协议运行时校验", result.stdout)
        self.assertIn("Agent output schema gate", result.stdout)
        self.assertIn("/api/demo/research", result.stdout)

    def test_script_can_run_deterministic_runtime_verification(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json", "--run-e2e"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)
        runtime = payload["runtime_verification"]

        self.assertEqual(runtime["delivery"]["status"], "passed")
        self.assertTrue(runtime["delivery"]["handoff_ready"])
        self.assertGreater(runtime["delivery"]["embedded_images"], 0)
        self.assertTrue(runtime["delivery"]["handoff_manifest_exists"])
        self.assertEqual(runtime["delivery"]["handoff_manifest_assets"], runtime["delivery"]["asset_count"])
        self.assertEqual(runtime["delivery"]["handoff_manifest_images"], runtime["delivery"]["embedded_images"])
        self.assertEqual(runtime["delivery"]["handoff_manifest_shots"], runtime["delivery"]["shot_count"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_image_prompts"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_asset_identity_fields"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_asset_baseline_chain"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_shot_reference_images"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_shot_execution_notes"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_shot_production_package"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_production_lineage"])
        self.assertTrue(runtime["delivery"]["handoff_manifest_lineage_handoff_fields"])
        self.assertTrue(runtime["delivery"]["word_canvas_agent_handoff"])
        self.assertTrue(runtime["delivery"]["word_canvas_asset_file_references"])
        self.assertEqual(runtime["user_flow"]["status"], "passed")
        self.assertEqual(runtime["user_flow"]["final_stage"], "ready_for_handoff")
        self.assertTrue(runtime["user_flow"]["handoff_manifest_asset_baseline_chain"])
        self.assertTrue(runtime["user_flow"]["handoff_manifest_shot_production_package"])
        self.assertTrue(runtime["user_flow"]["production_lineage_handoff_fields"])
        self.assertGreater(runtime["user_flow"]["download_bytes"], 1000)
        self.assertGreater(runtime["user_flow"]["generated_images"], 0)
        stage_b = runtime["stage_b_product_loop"]
        self.assertEqual(stage_b["status"], "passed")
        self.assertTrue(stage_b["entry_modes_ready"])
        self.assertTrue(stage_b["cabinet_boundary_ready"])
        self.assertTrue(stage_b["multi_agent_outputs_ready"])
        self.assertTrue(stage_b["revision_loop_ready"])
        self.assertTrue(stage_b["downstream_handoff_ready"])
        self.assertEqual(
            {item["id"] for item in stage_b["requirements"]},
            {
                "entry_modes",
                "cabinet_boundary",
                "multi_agent_outputs",
                "revision_loop",
                "downstream_handoff",
            },
        )

    def test_markdown_mentions_runtime_verification_when_enabled(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown", "--run-e2e"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("运行时验证", result.stdout)
        self.assertIn("阶段 B 产品闭环", result.stdout)
        self.assertIn("ready_for_handoff", result.stdout)
        self.assertIn("shot_package=True", result.stdout)


if __name__ == "__main__":
    unittest.main()
