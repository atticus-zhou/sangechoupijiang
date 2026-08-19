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


if __name__ == "__main__":
    unittest.main()
