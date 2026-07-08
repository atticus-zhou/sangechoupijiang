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

    def test_office_protocol_api_declares_platform_contracts(self):
        response = self.client.get("/api/offices/protocols")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
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
        self.assertEqual(comic["artifact_contract"]["id_field"], "artifact_id")
        self.assertIn("source", comic["artifact_contract"]["required_metadata"])
        self.assertIn("responsible_agent", comic["artifact_contract"]["required_metadata"])
        self.assertIn("reference_chain", comic["artifact_contract"]["required_metadata"])

        research = protocols["research"]
        self.assertTrue(any(item["stage"] == "agent_workflow" for item in research["recovery_actions"]))

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
        artifact_uris = {item["type"]: item.get("uri", "") for item in payload["artifacts"]}
        self.assertIn("/api/demo/comic-production/files/", artifact_uris["word_canvas"])
        self.assertIn("/api/demo/comic-production/files/", artifact_uris["handoff_manifest"])
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


if __name__ == "__main__":
    unittest.main()
