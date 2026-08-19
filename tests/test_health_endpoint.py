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
        self.assertGreaterEqual(payload["office_count"], 2)
        self.assertIn("research", payload["office_ids"])
        self.assertIn("comic_production", payload["office_ids"])
        self.assertEqual(payload["checks"]["offices"], "/api/offices")
        self.assertNotIn("api_key", str(payload).lower())

    def test_api_health_alias_matches_root_health(self):
        root_payload = self.client.get("/health").json()
        api_payload = self.client.get("/api/health").json()

        self.assertEqual(api_payload, root_payload)

    def test_first_run_guide_is_public_safe_and_actionable(self):
        response = self.client.get("/api/first-run-guide")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["mode"], "guided_first_run")
        self.assertTrue(payload["public_safe"])
        self.assertFalse(payload["requires_model_credentials"])
        self.assertFalse(payload["calls_real_models"])

        paths = {item["id"]: item for item in payload["paths"]}
        self.assertEqual(set(paths), {"public_demo", "local_real_use", "developer_extension"})
        self.assertFalse(paths["public_demo"]["requires_model_credentials"])
        self.assertFalse(paths["public_demo"]["calls_real_models"])
        self.assertTrue(paths["local_real_use"]["requires_model_credentials"])
        self.assertTrue(paths["local_real_use"]["calls_real_models"])
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
