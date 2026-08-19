import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.llm.providers import ModelConfig
from src.web.app import app


def text_config() -> ModelConfig:
    return ModelConfig(provider="deepseek", model="deepseek-chat", api_key="text-key")


def image_config() -> ModelConfig:
    return ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="image-key")


def vision_config() -> ModelConfig:
    return ModelConfig(provider="dashscope", model="qwen-vl-plus", api_key="vision-key")


def missing_config() -> ModelConfig:
    return ModelConfig(provider="deepseek", model="deepseek-chat", api_key="")


class OfficePreflightApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_comic_production_preflight_reports_ready_when_required_capabilities_exist(self):
        def fake_get_model_config(agent, office_id=""):
            self.assertEqual(office_id, "comic_production")
            if agent == "gongbu":
                return image_config()
            if agent == "xingbu":
                return vision_config()
            return text_config()

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config):
            response = self.client.get("/api/offices/comic_production/preflight")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["office_id"], "comic_production")
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["next_action"], "可以开始工作。")
        self.assertTrue(all(item["status"] == "ok" for item in payload["capabilities"]))
        contract = payload["model_capability_contract"]
        self.assertEqual(contract["source"], "docs/MODEL_CAPABILITY_MATRIX.json")
        self.assertEqual(contract["office_id"], "comic_production")
        self.assertEqual(contract["capability_counts"]["image_generation"], 1)
        self.assertEqual(contract["capability_counts"]["vision_understanding"], 1)
        self.assertNotIn("text-key", str(contract))

    def test_comic_production_preflight_locates_missing_image_and_vision_models(self):
        def fake_get_model_config(agent, office_id=""):
            if agent == "gongbu":
                return text_config()
            if agent == "xingbu":
                return missing_config()
            return text_config()

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config):
            response = self.client.get("/api/offices/comic_production/preflight")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "partial")
        self.assertIn("可以先完成故事、视觉母版、资产拆解和提示词", payload["summary"])
        by_id = {item["id"]: item for item in payload["capabilities"]}

        self.assertEqual(by_id["image_generation"]["status"], "missing")
        self.assertEqual(by_id["image_generation"]["office_id"], "comic_production")
        self.assertEqual(by_id["image_generation"]["owner_type"], "department")
        self.assertEqual(by_id["image_generation"]["owner_label"], "工部")
        self.assertEqual(by_id["image_generation"]["model_kind"], "生图模型")
        self.assertIn("模型页面", by_id["image_generation"]["next_action"])
        self.assertIn("工部生图模型", by_id["image_generation"]["next_action"])

        self.assertEqual(by_id["visual_review"]["status"], "missing")
        self.assertEqual(by_id["visual_review"]["owner_label"], "刑部")
        self.assertEqual(by_id["visual_review"]["model_kind"], "视觉模型")
        self.assertIn("刑部视觉模型", by_id["visual_review"]["next_action"])
        self.assertEqual(payload["model_capability_contract"]["full_mode"], "production_canvas_with_images_and_visual_review")

    def test_model_capability_matrix_api_is_no_key_and_office_scoped(self):
        matrix_response = self.client.get("/api/model-capability-matrix")
        self.assertEqual(matrix_response.status_code, 200)
        matrix = matrix_response.json()
        self.assertEqual(matrix["schema"], "three_cobblers_model_capability_matrix_v1")
        self.assertIn("comic_production", matrix["offices"])
        self.assertIn("research", matrix["offices"])
        self.assertNotIn("api_key", str(matrix).lower())

        office_response = self.client.get("/api/offices/comic/model-capabilities")
        self.assertEqual(office_response.status_code, 200)
        office = office_response.json()
        self.assertEqual(office["office_id"], "comic_production")
        by_department = {
            item["department_id"]: item["required_capability"]
            for item in office["departments"]
        }
        self.assertEqual(by_department["gongbu"], "image_generation")
        self.assertEqual(by_department["xingbu"], "vision_understanding")
        self.assertIn("safe_key_rule", office)

    def test_comic_production_preflight_blocks_when_core_text_model_is_missing(self):
        def fake_get_model_config(agent, office_id=""):
            if agent == "zhongshu":
                return missing_config()
            if agent == "gongbu":
                return image_config()
            if agent == "xingbu":
                return vision_config()
            return text_config()

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config):
            response = self.client.get("/api/offices/comic_production/preflight")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("中书省文本模型", payload["blocking_reasons"])
        self.assertIn("先配置中书省", payload["next_action"])
        by_id = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(by_id["story_planning"]["owner_label"], "中书省")
        self.assertEqual(by_id["story_planning"]["model_kind"], "文本模型")

    def test_comic_production_readiness_api_reports_product_conditions(self):
        response = self.client.get("/api/offices/comic_production/readiness")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["office_id"], "comic_production")
        self.assertEqual(payload["mode"], "real_product_with_no_key_demo")
        self.assertEqual(payload["status"], "ready_with_demo")
        checks = {item["id"]: item for item in payload["checks"]}
        self.assertIn("workflow_state", checks)
        self.assertIn("downloadable_delivery", checks)
        self.assertIn("failure_handling", checks)

    def test_comic_real_production_readiness_reports_full_ready_without_calling_models(self):
        def fake_get_model_config(agent, office_id=""):
            self.assertEqual(office_id, "comic_production")
            if agent == "gongbu":
                return image_config()
            if agent == "xingbu":
                return vision_config()
            return text_config()

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config):
            response = self.client.get("/api/offices/comic_production/real-production-readiness")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "real_production_start_readiness")
        self.assertEqual(payload["status"], "ready_for_real_run")
        self.assertTrue(payload["can_start_full_production"])
        self.assertTrue(payload["can_start_limited_planning"])
        self.assertFalse(payload["calls_real_models"])
        self.assertFalse(payload["requires_api_key_to_check"])
        self.assertFalse(payload["writes_workspace"])
        self.assertGreaterEqual(len(payload["operator_checklist"]), 5)
        self.assertGreaterEqual(payload["handoff_inventory"]["manifest_count"], 1)
        self.assertEqual(payload["handoff_inventory"]["production_verified_count"], 0)
        self.assertNotIn("text-key", str(payload))
        self.assertNotIn("image-key", str(payload))
        self.assertNotIn("vision-key", str(payload))

    def test_comic_real_production_readiness_allows_limited_planning_without_image_or_vision(self):
        def fake_get_model_config(agent, office_id=""):
            if agent == "gongbu":
                return text_config()
            if agent == "xingbu":
                return missing_config()
            return text_config()

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config):
            response = self.client.get("/api/offices/comic_production/real-production-readiness")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "limited_planning_only")
        self.assertFalse(payload["can_start_full_production"])
        self.assertTrue(payload["can_start_limited_planning"])
        self.assertIn("不能生成完整带图片", payload["summary"])
        by_id = {item["id"]: item for item in payload["required_capabilities"]}
        self.assertEqual(by_id["image_generation"]["status"], "missing")
        self.assertEqual(by_id["visual_review"]["status"], "missing")

    def test_comic_real_production_readiness_blocks_without_core_text_model(self):
        def fake_get_model_config(agent, office_id=""):
            if agent == "zhongshu":
                return missing_config()
            if agent == "gongbu":
                return image_config()
            if agent == "xingbu":
                return vision_config()
            return text_config()

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config):
            response = self.client.get("/api/offices/comic_production/real-production-readiness")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["can_start_full_production"])
        self.assertFalse(payload["can_start_limited_planning"])
        self.assertIn("中书省文本模型", payload["blocking_reasons"])

    def test_office_protocol_api_declares_platform_contracts(self):
        response = self.client.get("/api/offices/protocols")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("creation_template", payload)
        self.assertIn("extension_blueprint", payload)
        self.assertEqual(payload["launch_matrix_summary"]["office_count"], 3)
        self.assertEqual(payload["launch_matrix_summary"]["primary_allowed_count"], 1)
        launch_matrix = {item["office_id"]: item for item in payload["launch_matrix"]}
        self.assertTrue(launch_matrix["comic_production"]["can_show_publicly"])
        self.assertTrue(launch_matrix["comic_production"]["primary_allowed"])
        self.assertFalse(launch_matrix["comic"]["can_show_publicly"])
        self.assertIn("legacy_migration_required", launch_matrix["comic"]["blocked_by"])
        self.assertIn("required_profile_fields", payload["creation_template"])
        self.assertIn("recovery_actions", payload["creation_template"]["required_profile_fields"])
        self.assertIn("no_key_demo", payload["creation_template"]["required_launch_gates"])
        blueprint_steps = {item["id"] for item in payload["extension_blueprint"]["implementation_steps"]}
        self.assertIn("register_profile", blueprint_steps)
        self.assertIn("isolate_runtime", blueprint_steps)
        self.assertIn("build_no_key_demo", blueprint_steps)
        self.assertIn("wire_schema_and_recovery", blueprint_steps)
        protocols = {item["office_id"]: item for item in payload["protocols"]}

        self.assertIn("comic_production", protocols)
        self.assertIn("research", protocols)

        comic = protocols["comic_production"]
        self.assertIn("完整剧本", comic["input_types"])
        self.assertIn("Word 制片画布", comic["output_types"])
        self.assertTrue(any(item["agent"] == "zhongshu" and item["model_kind"] == "text" for item in comic["model_requirements"]))
        self.assertTrue(any(item["agent"] == "gongbu" and item["model_kind"] == "image" for item in comic["model_requirements"]))
        self.assertTrue(any(item["id"] == "story_confirmation" for item in comic["human_checkpoints"]))
        self.assertTrue(any(item["id"] == "asset_review" for item in comic["human_checkpoints"]))
        self.assertTrue(any(item["stage"] == "document_generation" for item in comic["recovery_actions"]))
        schema_ids = {item["schema_id"] for item in comic["schema_gates"]}
        self.assertIn("comic_contract", schema_ids)
        self.assertIn("asset_manifest", schema_ids)
        self.assertIn("shot_cards", schema_ids)
        self.assertEqual(comic["artifact_contract"]["id_field"], "artifact_id")
        self.assertIn("source", comic["artifact_contract"]["required_metadata"])
        self.assertIn("responsible_agent", comic["artifact_contract"]["required_metadata"])
        self.assertIn("reference_chain", comic["artifact_contract"]["required_metadata"])

        research = protocols["research"]
        self.assertTrue(any(item["stage"] == "agent_workflow" for item in research["recovery_actions"]))

    def test_office_launch_gate_api_returns_productization_audit(self):
        response = self.client.get("/api/offices/comic_production/launch-gates")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["office_id"], "comic_production")
        self.assertEqual(payload["status"], "ready")
        gates = {gate["id"]: gate for gate in payload["gates"]}
        self.assertIn("no_key_demo", gates)
        self.assertEqual(gates["no_key_demo"]["status"], "passed")
        self.assertTrue(gates["no_key_demo"]["evidence"])
        self.assertIn("next_action", gates["no_key_demo"])

    def test_office_launch_gate_api_marks_legacy_comic_as_not_ready(self):
        response = self.client.get("/api/offices/comic/launch-gates")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["office_id"], "comic")
        self.assertEqual(payload["status"], "needs_work")
        self.assertEqual(payload["role"], "legacy")
        self.assertEqual(payload["legacy_migration"]["target_office_id"], "comic_production")
        self.assertIn("AI漫剧制片办公室", payload["legacy_migration"]["target_office_name"])
        gates = {gate["id"]: gate for gate in payload["gates"]}
        self.assertEqual(gates["no_key_demo"]["status"], "needs_work")
        self.assertTrue(gates["no_key_demo"]["next_action"])

    def test_comic_production_demo_api_is_no_key_and_read_only(self):
        with patch("src.web.app.config_manager.get_model_config") as get_model_config, \
             patch("src.web.app.config_manager.create_workspace") as create_workspace:
            response = self.client.get("/api/demo/comic-production")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "no_key_demo")
        self.assertEqual(payload["office_id"], "comic_production")
        self.assertFalse(payload["uses_real_models"])
        self.assertFalse(payload["api_key_required"])
        self.assertFalse(payload["writes_workspace"])
        self.assertGreaterEqual(payload["asset_count"], 1)
        self.assertGreaterEqual(payload["shot_count"], 1)
        self.assertTrue(payload["stages"])
        self.assertTrue(payload["artifacts"])
        self.assertTrue(payload["quality_gates"])
        self.assertGreaterEqual(len(payload["viewer_path"]), 3)
        self.assertGreaterEqual(len(payload["proof_points"]), 3)
        self.assertIn("先看故事", payload["viewer_path"][0]["title"])
        self.assertIn("Word", " ".join(payload["proof_points"]))
        gate_ids = {item["id"] for item in payload["quality_gates"]}
        self.assertIn("no_key_read_only", gate_ids)
        self.assertIn("downloadable_delivery", gate_ids)
        self.assertIn("reference_chain", gate_ids)
        self.assertIn("downstream_handoff", gate_ids)
        self.assertIn("honest_quality_claim", gate_ids)
        self.assertTrue(all(item["status"] == "passed" for item in payload["quality_gates"]))
        benchmark = payload["quality_benchmark"]
        self.assertEqual(benchmark["status"], "demo_structure_verified")
        self.assertEqual(benchmark["package_quality_score"], 100)
        self.assertTrue(benchmark["package_quality_ready"])
        self.assertFalse(benchmark["production_quality_verified"])
        self.assertEqual(benchmark["recommended_recovery"], {})
        artifact_uris = {item["type"]: item.get("uri", "") for item in payload["artifacts"]}
        self.assertIn("/api/demo/comic-production/files/", artifact_uris["word_canvas"])
        self.assertIn("/api/demo/comic-production/files/", artifact_uris["handoff_manifest"])
        self.assertEqual(artifact_uris["downstream_handoff_gate"], "docs/COMIC_DOWNSTREAM_HANDOFF.md")
        self.assertTrue(artifact_uris["word_canvas"].endswith("/word_canvas.docx"))
        self.assertTrue(artifact_uris["handoff_manifest"].endswith("/handoff_manifest.json"))
        get_model_config.assert_not_called()
        create_workspace.assert_not_called()

    def test_comic_production_demo_downloads_fixed_delivery_files(self):
        response = self.client.get("/api/demo/comic-production")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        artifacts = {item["type"]: item for item in payload["artifacts"]}

        word = self.client.get(artifacts["word_canvas"]["uri"])
        manifest = self.client.get(artifacts["handoff_manifest"]["uri"])

        self.assertEqual(word.status_code, 200)
        self.assertGreater(len(word.content), 1000)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            word.headers.get("content-type", ""),
        )
        self.assertEqual(manifest.status_code, 200)
        self.assertIn("application/json", manifest.headers.get("content-type", ""))
        self.assertIn("word_canvas", manifest.json())

    def test_research_demo_api_is_no_key_and_read_only(self):
        with patch("src.web.app.config_manager.get_model_config") as get_model_config, \
             patch("src.web.app.config_manager.create_workspace") as create_workspace:
            response = self.client.get("/api/demo/research")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "no_key_demo")
        self.assertEqual(payload["office_id"], "research")
        self.assertFalse(payload["uses_real_models"])
        self.assertFalse(payload["api_key_required"])
        self.assertFalse(payload["writes_workspace"])
        self.assertGreaterEqual(payload["source_count"], 1)
        self.assertGreaterEqual(payload["data_point_count"], 1)
        self.assertGreaterEqual(payload["competitor_count"], 1)
        self.assertTrue(payload["stages"])
        self.assertTrue(payload["quality_gates"])
        self.assertGreaterEqual(len(payload["viewer_path"]), 3)
        self.assertGreaterEqual(len(payload["proof_points"]), 3)
        self.assertGreaterEqual(len(payload["evidence_boundaries"]["covered_in_demo"]), 4)
        self.assertGreaterEqual(len(payload["evidence_boundaries"]["requires_human_or_account"]), 3)
        self.assertIn("不宣称全自动", payload["evidence_boundaries"]["public_demo_boundary"])
        self.assertGreaterEqual(len(payload["evidence_handoff"]), 3)
        self.assertTrue(all(item["owner"] and item["target_evidence"] and item["upgrades"] for item in payload["evidence_handoff"]))
        self.assertIn("先看目标", payload["viewer_path"][0]["title"])
        self.assertIn("证据", " ".join(payload["proof_points"]))
        self.assertGreaterEqual(len(payload["deliverable_reading_guide"]), 3)
        self.assertTrue(all(item["look_for"] and item["proves"] for item in payload["deliverable_reading_guide"]))
        self.assertIn(
            "/api/demo/research/claim-report",
            {item["uri"] for item in payload["deliverable_reading_guide"]},
        )
        self.assertTrue(
            all(
                item["uri"].startswith("/api/demo/research/files/")
                or item["uri"] == "/api/demo/research/claim-report"
                for item in payload["deliverable_reading_guide"]
            )
        )
        gate_ids = {item["id"] for item in payload["quality_gates"]}
        self.assertIn("no_key_read_only", gate_ids)
        self.assertIn("traceable_sources", gate_ids)
        self.assertIn("downloadable_delivery", gate_ids)
        self.assertTrue(all(item["status"] == "passed" for item in payload["quality_gates"]))
        artifact_uris = {item["type"]: item.get("uri", "") for item in payload["artifacts"]}
        self.assertTrue(artifact_uris["report_markdown"].endswith("/report.md"))
        self.assertTrue(artifact_uris["evidence_manifest"].endswith("/evidence_manifest.json"))
        get_model_config.assert_not_called()
        create_workspace.assert_not_called()

    def test_research_demo_downloads_fixed_delivery_files(self):
        response = self.client.get("/api/demo/research")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        artifacts = {item["type"]: item for item in payload["artifacts"]}

        report = self.client.get(artifacts["report_markdown"]["uri"])
        manifest = self.client.get(artifacts["evidence_manifest"]["uri"])

        self.assertEqual(report.status_code, 200)
        self.assertIn("text/markdown", report.headers.get("content-type", ""))
        self.assertIn("民用无人机", report.text)
        self.assertEqual(manifest.status_code, 200)
        self.assertIn("application/json", manifest.headers.get("content-type", ""))
        self.assertIn("sources", manifest.json())
        self.assertIn("screenshot_plan", manifest.json())
        self.assertIn("evidence_handoff", manifest.json())
        self.assertGreaterEqual(len(manifest.json()["evidence_handoff"]), 3)


if __name__ == "__main__":
    unittest.main()
