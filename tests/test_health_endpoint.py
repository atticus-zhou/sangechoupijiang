import unittest

from fastapi.testclient import TestClient

from src.web.app import app


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint_is_public_safe_and_no_key(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "sangechoupijiang")
        self.assertTrue(payload["public_safe"])
        self.assertFalse(payload["requires_model_credentials"])
        self.assertFalse(payload["calls_real_models"])
        self.assertEqual(payload["display_name"], "三个臭皮匠")
        self.assertGreaterEqual(payload["office_count"], 2)
        self.assertIn("research", payload["office_ids"])
        self.assertIn("comic_production", payload["office_ids"])
        self.assertNotIn("comic", payload["office_ids"])
        self.assertEqual(payload["legacy_office_ids"], ["comic"])
        self.assertEqual(payload["checks"]["offices"], "/api/offices")
        self.assertEqual(payload["checks"]["offices_with_legacy"], "/api/offices?include_legacy=true")
        self.assertNotIn("api_key", str(payload).lower())

    def test_api_health_alias_matches_root_health(self):
        root_payload = self.client.get("/health").json()
        api_payload = self.client.get("/api/health").json()

        self.assertEqual(api_payload, root_payload)

    def test_office_list_hides_legacy_comic_by_default(self):
        public_payload = self.client.get("/api/offices").json()
        public_ids = {office["id"] for office in public_payload["offices"]}

        self.assertIn("research", public_ids)
        self.assertIn("comic_production", public_ids)
        self.assertNotIn("comic", public_ids)
        self.assertTrue(all(office["publicly_listed"] for office in public_payload["offices"]))

        legacy_payload = self.client.get("/api/offices?include_legacy=true").json()
        legacy_by_id = {office["id"]: office for office in legacy_payload["offices"]}
        self.assertIn("comic", legacy_by_id)
        self.assertEqual(legacy_by_id["comic"]["role"], "legacy")
        self.assertEqual(legacy_by_id["comic"]["legacy_migration"]["target_office_id"], "comic_production")

    def test_first_run_guide_is_public_safe_and_actionable(self):
        response = self.client.get("/api/first-run-guide")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["mode"], "guided_first_run")
        self.assertTrue(payload["public_safe"])
        self.assertFalse(payload["requires_model_credentials"])
        self.assertFalse(payload["calls_real_models"])
        self.assertEqual(payload["title"], "第一次使用应该先做什么")
        self.assertIn("无 Key 演示", payload["summary"])
        self.assertIn("逐个部门测试", payload["primary_next_action"])

        paths = {item["id"]: item for item in payload["paths"]}
        self.assertEqual(set(paths), {"public_demo", "local_real_use", "developer_extension"})
        self.assertFalse(paths["public_demo"]["requires_model_credentials"])
        self.assertFalse(paths["public_demo"]["calls_real_models"])
        self.assertEqual(paths["public_demo"]["label"], "先看无 Key 演示")
        self.assertTrue(paths["local_real_use"]["requires_model_credentials"])
        self.assertTrue(paths["local_real_use"]["calls_real_models"])
        self.assertEqual(paths["local_real_use"]["label"], "配置本地真实使用")
        self.assertEqual(paths["developer_extension"]["label"], "开发新办公室")
        self.assertGreaterEqual(len(paths["developer_extension"]["first_actions"]), 3)

        quick_checks = {item["id"] for item in payload["quick_checks"]}
        self.assertIn("runtime_health", quick_checks)
        self.assertIn("local_doctor", quick_checks)
        self.assertIn("model_guidance", quick_checks)
        self.assertIn("onboarding_packet", quick_checks)
        self.assertIn("release_gate", quick_checks)
        serialized = str(payload).lower()
        self.assertNotIn("password", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("sk-", serialized)


if __name__ == "__main__":
    unittest.main()
