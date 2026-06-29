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
        self.assertEqual(payload["mode"], "real_product_without_demo")
        self.assertEqual(payload["status"], "ready_without_demo")
        checks = {item["id"]: item for item in payload["checks"]}
        self.assertIn("workflow_state", checks)
        self.assertIn("downloadable_delivery", checks)
        self.assertIn("failure_handling", checks)


if __name__ == "__main__":
    unittest.main()
