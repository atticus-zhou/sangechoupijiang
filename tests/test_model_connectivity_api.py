import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.llm.providers import LLMResponse, ModelConfig
from src.web.app import app


class ModelConnectivityApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_model_probe_uses_office_scoped_department_config(self):
        calls = []

        def fake_get_model_config(agent, office_id=""):
            calls.append((agent, office_id))
            return ModelConfig(
                provider="deepseek",
                model="deepseek-chat",
                api_key="test-key",
                temperature=0.8,
                max_tokens=4096,
            )

        fake_provider = AsyncMock()
        fake_provider.chat.return_value = LLMResponse(content="pong", model="deepseek-chat", tokens_used=1)

        with patch("src.model_connectivity.LLMFactory.create", return_value=fake_provider), patch(
            "src.web.app.config_manager.get_model_config",
            side_effect=fake_get_model_config,
        ):
            response = self.client.post("/api/config/models/hubu/test?office_id=comic")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["office_id"], "comic")
        self.assertEqual(payload["agent"], "hubu")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(calls, [("hubu", "comic")])

    def test_model_probe_reports_missing_key_without_calling_provider(self):
        with patch(
            "src.web.app.config_manager.get_model_config",
            return_value=ModelConfig(provider="deepseek", model="deepseek-chat", api_key=""),
        ), patch("src.model_connectivity.LLMFactory.create") as create_provider:
            response = self.client.post("/api/config/models/hubu/test?office_id=comic")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "missing_key")
        self.assertIn("api_key", payload["detail"])
        create_provider.assert_not_called()

    def test_all_model_probe_returns_each_department_for_current_office(self):
        def fake_get_model_config(agent, office_id=""):
            return ModelConfig(provider="deepseek", model="deepseek-chat", api_key="test-key")

        async def fake_probe(agent, office_id, config):
            status = "missing_key" if agent == "hubu" else "ok"
            return {
                "office_id": office_id,
                "agent": agent,
                "provider": config.provider,
                "model": config.model,
                "kind": "chat",
                "has_key": bool(config.api_key),
                "status": status,
                "detail": "",
            }

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config), patch(
            "src.web.app.probe_model_connectivity",
            side_effect=fake_probe,
        ):
            response = self.client.post("/api/config/models/test?office_id=comic")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["office_id"], "comic")
        self.assertEqual(payload["status"], "needs_attention")
        self.assertEqual(len(payload["results"]), 9)
        self.assertEqual({item["office_id"] for item in payload["results"]}, {"comic"})

    def test_model_config_reads_never_expose_api_keys(self):
        config = {
            "models": {
                "hubu": {"provider": "deepseek", "model": "deepseek-chat", "api_key": "global-secret"},
            },
            "office_models": {
                "comic": {
                    "hubu": {"api_key": "comic-secret"},
                }
            },
        }

        with patch("src.web.app.config_manager.load_yaml", return_value=config):
            response = self.client.get("/api/config/models?office_id=comic")

        self.assertEqual(response.status_code, 200)
        model = response.json()["models"]["hubu"]
        self.assertNotIn("api_key", model)
        self.assertTrue(model["has_api_key"])
        self.assertEqual(model["api_key_hint"], "已配置")

    def test_full_config_read_never_exposes_api_keys(self):
        config = {
            "models": {"hubu": {"provider": "deepseek", "api_key": "global-secret"}},
            "office_models": {"comic": {"gongbu": {"provider": "doubao", "api_key": "comic-secret"}}},
            "system": {"language": "zh-CN"},
        }

        with patch("src.web.app.config_manager.load_yaml", return_value=config):
            response = self.client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("api_key", body["models"]["hubu"])
        self.assertNotIn("api_key", body["office_models"]["comic"]["gongbu"])
        self.assertTrue(body["models"]["hubu"]["has_api_key"])
        self.assertEqual(body["system"], {"language": "zh-CN"})

    def test_provider_change_clears_existing_key_in_office_scope(self):
        config = {
            "models": {},
            "office_models": {
                "comic": {
                    "hubu": {
                        "provider": "doubao",
                        "model": "doubao-seedream-5",
                        "api_key": "old-provider-key",
                    }
                }
            },
        }
        saved = {}

        with patch("src.web.app.config_manager.load_yaml", return_value=config), patch(
            "src.web.app.config_manager.save_yaml",
            side_effect=lambda value: saved.update(value),
        ):
            response = self.client.put(
                "/api/config/models/hubu?office_id=comic",
                json={"provider": "deepseek"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["config"]["provider"], "deepseek")
        self.assertNotIn("api_key", payload["config"])
        self.assertFalse(payload["config"]["has_api_key"])
        self.assertIn("warnings", payload)
        self.assertEqual(saved["office_models"]["comic"]["hubu"]["api_key"], "")


if __name__ == "__main__":
    unittest.main()
