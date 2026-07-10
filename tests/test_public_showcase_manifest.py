import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from src.web.app import app


class PublicShowcaseManifestTests(unittest.TestCase):
    def test_public_showcase_manifest_packages_product_story_and_demo_links(self):
        client = TestClient(app)
        response = client.get("/api/demo/public-showcase")

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["mode"], "public_no_key_showcase")
        self.assertEqual(payload["product_name"], "三个臭皮匠")
        self.assertIn("多 Agent", payload["positioning"])
        self.assertFalse(payload["requires_api_key"])
        self.assertFalse(payload["calls_real_models"])
        self.assertTrue(payload["safe_for_public_portfolio"])
        self.assertIn("不要把个人 API Key", "\n".join(payload["safety_boundaries"]))

        audience_ids = {item["id"] for item in payload["audience_paths"]}
        self.assertEqual(audience_ids, {"interviewer", "developer", "user"})
        for path in payload["audience_paths"]:
            self.assertGreaterEqual(len(path["steps"]), 3)
            self.assertTrue(path["takeaway"])

        demos = {item["office_id"]: item for item in payload["featured_demos"]}
        self.assertEqual(set(demos), {"comic_production", "research"})
        self.assertEqual(demos["comic_production"]["demo_uri"], "/api/demo/comic-production")
        self.assertEqual(demos["research"]["demo_uri"], "/api/demo/research")
        for demo in demos.values():
            self.assertGreaterEqual(len(demo["viewer_path"]), 3)
            self.assertGreaterEqual(len(demo["proof_points"]), 3)
            self.assertGreaterEqual(len(demo["downloads"]), 2)
            for item in demo["downloads"]:
                self.assertTrue(item["uri"].startswith("/api/demo/"))
                self.assertEqual(item["status"], "downloadable")

        embed = payload["portfolio_embed"]
        self.assertEqual(embed["repository_url"], "https://github.com/atticus-zhou/sangechoupijiang")
        self.assertIn("办公室大厅", embed["office_hall"]["title"])
        self.assertGreaterEqual(len(embed["workflow_showcase"]), 4)
        self.assertTrue(any(item["kind"] == "screenshot_target" for item in embed["workflow_showcase"]))
        self.assertGreaterEqual(len(embed["sample_deliverables"]), 4)
        self.assertTrue(all(item["uri"].startswith("/api/demo/") for item in embed["sample_deliverables"]))

        public_deployment = payload["public_deployment"]
        self.assertEqual(public_deployment["mode"], "demo_only")
        self.assertFalse(public_deployment["allows_real_model_calls"])
        self.assertFalse(public_deployment["allows_workspace_writes"])
        self.assertEqual(public_deployment["allowed_route_prefixes"], ["/api/demo"])
        self.assertIn("config.yaml", " ".join(public_deployment["forbidden_public_assets"]))

    def test_public_showcase_manifest_download_links_are_real(self):
        client = TestClient(app)
        payload = client.get("/api/demo/public-showcase").json()

        for demo in payload["featured_demos"]:
            for item in demo["downloads"]:
                response = client.get(item["uri"])
                self.assertEqual(response.status_code, 200)
                self.assertGreater(len(response.content), 20)



    def test_comic_demo_delivery_generation_uses_cross_process_lock(self):
        source = Path("src/web/app.py").read_text(encoding="utf-8")

        self.assertIn("def _demo_delivery_lock", source)
        self.assertIn("demo_delivery.lock", source)
        self.assertIn("with _demo_delivery_lock", source)

if __name__ == "__main__":
    unittest.main()
