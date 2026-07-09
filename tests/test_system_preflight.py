import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.llm.providers import ModelConfig
from src.web.app import app


class FakeConfigManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.config_path = base_dir / "config.yaml"
        self.db_path = base_dir / "user_data" / "config.db"

    def get_model_config(self, agent: str, office_id: str = "") -> ModelConfig:
        if office_id == "comic_production":
            if agent == "gongbu":
                return ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="image-key")
            if agent == "xingbu":
                return ModelConfig(provider="dashscope", model="qwen-vl-plus", api_key="vision-key")
            return ModelConfig(provider="deepseek", model="deepseek-chat", api_key="text-key")
        return ModelConfig(provider="deepseek", model="deepseek-chat", api_key="text-key")


class SystemPreflightTests(unittest.TestCase):
    def test_system_preflight_reports_runtime_config_database_output_and_models(self):
        from src.system_preflight import build_system_preflight

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base_dir = Path(tmp)
            manager = FakeConfigManager(base_dir)
            manager.config_path.write_text("models: {}\n", encoding="utf-8")
            manager.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(manager.db_path) as conn:
                conn.execute("CREATE TABLE config_store (key TEXT PRIMARY KEY, value TEXT)")

            result = build_system_preflight(manager, base_dir=base_dir)

        self.assertEqual(result["status"], "ready")
        self.assertIn("Python", result["summary"])
        self.assertIn("配置", result["summary"])
        self.assertIn("AI 漫剧制片办公室", result["next_action"])
        by_id = {item["id"]: item for item in result["checks"]}
        for check_id in [
            "python_runtime",
            "config_file",
            "database",
            "output_directory",
            "model_configuration",
        ]:
            self.assertIn(check_id, by_id)
            self.assertEqual(by_id[check_id]["status"], "ok")
            self.assertIn("scope", by_id[check_id])
            self.assertIn("impact", by_id[check_id])
            self.assertIn("next_action", by_id[check_id])
        self.assertEqual(by_id["config_file"]["title"], "配置文件")
        self.assertEqual(by_id["database"]["title"], "本地数据库")
        self.assertEqual(by_id["output_directory"]["title"], "输出目录")
        self.assertEqual(result["available_modes"][0]["id"], "no_key_demo")
        self.assertTrue(any(mode["id"] == "comic_full_production" for mode in result["available_modes"]))
        self.assertEqual(result["limited_features"], [])

    def test_system_preflight_blocks_with_actionable_missing_config_and_database(self):
        from src.system_preflight import build_system_preflight

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base_dir = Path(tmp)
            manager = FakeConfigManager(base_dir)

            result = build_system_preflight(manager, base_dir=base_dir)

        self.assertEqual(result["status"], "blocked")
        by_id = {item["id"]: item for item in result["checks"]}
        self.assertEqual(by_id["config_file"]["status"], "blocked")
        self.assertIn("config.yaml", by_id["config_file"]["next_action"])
        self.assertEqual(by_id["database"]["status"], "blocked")
        self.assertIn("user_data", by_id["database"]["next_action"])
        self.assertIn("config_file", result["blocking_reasons"])
        self.assertIn("database", result["blocking_reasons"])
        self.assertEqual(result["available_modes"][0]["id"], "no_key_demo")
        self.assertTrue(any(feature["id"] == "local_real_mode" for feature in result["limited_features"]))

    def test_system_preflight_explains_partial_model_modes_and_unavailable_features(self):
        from src.system_preflight import build_system_preflight

        class PartialModelManager(FakeConfigManager):
            def get_model_config(self, agent: str, office_id: str = "") -> ModelConfig:
                if agent in {"gongbu", "xingbu"}:
                    return ModelConfig(provider="", model="", api_key="")
                return ModelConfig(provider="deepseek", model="deepseek-chat", api_key="text-key")

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base_dir = Path(tmp)
            manager = PartialModelManager(base_dir)
            manager.config_path.write_text("models: {}\n", encoding="utf-8")
            manager.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(manager.db_path) as conn:
                conn.execute("CREATE TABLE config_store (key TEXT PRIMARY KEY, value TEXT)")

            result = build_system_preflight(manager, base_dir=base_dir)

        self.assertEqual(result["status"], "partial")
        mode_ids = [mode["id"] for mode in result["available_modes"]]
        self.assertIn("comic_story_and_prompts", mode_ids)
        self.assertNotIn("comic_full_production", mode_ids)
        feature_ids = [feature["id"] for feature in result["limited_features"]]
        self.assertIn("image_generation", feature_ids)
        self.assertIn("visual_review", feature_ids)
        self.assertTrue(any("工部" in feature["reason"] for feature in result["limited_features"]))

    def test_system_preflight_api_returns_startup_checks(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base_dir = Path(tmp)
            manager = FakeConfigManager(base_dir)
            manager.config_path.write_text("models: {}\n", encoding="utf-8")
            manager.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(manager.db_path) as conn:
                conn.execute("CREATE TABLE config_store (key TEXT PRIMARY KEY, value TEXT)")

            with (
                patch("src.web.app.config_manager", manager),
                patch("src.web.app.APP_BASE_DIR", base_dir),
            ):
                response = TestClient(app).get("/api/system/preflight")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["python"]["executable"], sys.executable)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(any(item["id"] == "output_directory" for item in payload["checks"]))


if __name__ == "__main__":
    unittest.main()
