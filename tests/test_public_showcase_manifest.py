import json
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
        comic_benchmark = demos["comic_production"]["quality_benchmark"]
        self.assertEqual(comic_benchmark["status"], "demo_structure_verified")
        self.assertEqual(comic_benchmark["package_quality_score"], 100)
        self.assertFalse(comic_benchmark["production_quality_verified"])
        prompt_quality = comic_benchmark["prompt_quality_summary"]
        self.assertEqual(prompt_quality["status"], "ready")
        self.assertEqual(prompt_quality["clean_asset_prompt_count"], prompt_quality["asset_prompt_count"])
        self.assertEqual(prompt_quality["director_prompt_count"], prompt_quality["shot_prompt_count"])
        self.assertEqual(prompt_quality["issue_count"], 0)
        self.assertIn(
            "honest_quality_claim",
            {item["id"] for item in demos["comic_production"]["quality_gates"]},
        )
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
        release_badge = embed["release_badge"]
        self.assertEqual(release_badge["status"], "safe_public_demo")
        self.assertEqual(release_badge["mode"], "demo_only")
        self.assertIn("可公开展示", release_badge["label"])
        self.assertFalse(release_badge["can_claim_real_quality"])
        self.assertIn("verify_release_readiness.py", release_badge["primary_gate"])
        self.assertGreaterEqual(len(release_badge["signals"]), 5)
        self.assertTrue(any(item["label"] == "真实画质声明" for item in release_badge["signals"]))
        self.assertGreaterEqual(len(embed["workflow_showcase"]), 4)
        self.assertTrue(any(item["kind"] == "screenshot_target" for item in embed["workflow_showcase"]))
        fast_review = embed["fast_review_route"]
        self.assertEqual([item["order"] for item in fast_review], [1, 2, 3, 4])
        fast_review_text = json.dumps(fast_review, ensure_ascii=False)
        self.assertIn("Word 制片画布", fast_review_text)
        self.assertIn("handoff manifest", fast_review_text)
        self.assertIn("声明边界", fast_review_text)
        self.assertTrue(all(item["viewer_action"] and item["proof"] and item["next_anchor"] for item in fast_review))
        self.assertGreaterEqual(len(embed["sample_deliverables"]), 6)
        self.assertTrue(all(item["uri"].startswith("/api/demo/") for item in embed["sample_deliverables"]))
        claim_deliverables = [
            item for item in embed["sample_deliverables"] if item["type"] == "real_production_claim"
        ]
        self.assertEqual(len(claim_deliverables), 1)
        self.assertEqual(claim_deliverables[0]["uri"], "/api/demo/comic-production/claim-report")
        self.assertFalse(claim_deliverables[0]["can_claim_real_quality"])
        self.assertIn("demo-only", claim_deliverables[0]["acceptance_signals"][0])
        research_claim_deliverables = [
            item for item in embed["sample_deliverables"] if item["type"] == "research_claim"
        ]
        self.assertEqual(len(research_claim_deliverables), 1)
        self.assertEqual(research_claim_deliverables[0]["uri"], "/api/demo/research/claim-report")
        self.assertIn("全自动会员级采集", " ".join(research_claim_deliverables[0]["acceptance_signals"]))
        self.assertGreaterEqual(len(embed["deliverable_reading_guide"]), 6)
        self.assertEqual([item["order"] for item in embed["deliverable_reading_guide"]], [1, 2, 3, 4, 5, 6])
        for item in embed["deliverable_reading_guide"]:
            self.assertTrue(item["uri"].startswith("/api/demo/"))
            self.assertTrue(item["look_for"])
            self.assertTrue(item["proves"])
        self.assertTrue(any("Word 制片画布" in item["title"] for item in embed["deliverable_reading_guide"]))
        self.assertTrue(any("handoff manifest" in item["title"] for item in embed["deliverable_reading_guide"]))
        self.assertTrue(any("交付盘点" in item["title"] for item in embed["deliverable_reading_guide"]))
        self.assertTrue(any("证据清单" in item["title"] for item in embed["deliverable_reading_guide"]))
        self.assertTrue(any("声明边界" in item["title"] for item in embed["deliverable_reading_guide"]))
        quick_start = embed["downstream_quick_start"]
        self.assertEqual([item["step"] for item in quick_start], [1, 2, 3, 4, 5])
        quick_start_text = json.dumps(quick_start, ensure_ascii=False)
        self.assertIn("锁定基础资产", quick_start_text)
        self.assertIn("逐镜头生成视频", quick_start_text)
        self.assertIn("质量复核", quick_start_text)
        for item in quick_start:
            self.assertTrue(item["owner"])
            self.assertGreaterEqual(len(item["input_refs"]), 2)
            self.assertTrue(item["action"])
            self.assertTrue(item["output"])
            self.assertTrue(item["acceptance"])
        inventory = embed["handoff_inventory"]
        self.assertEqual(inventory["uri"], "/api/demo/comic-production/handoff-inventory")
        self.assertGreaterEqual(inventory["manifest_count"], 1)
        self.assertEqual(inventory["production_verified_count"], 0)
        self.assertIn("真实模型质量", inventory["safe_public_claim"])
        claim = embed["real_production_claim"]
        self.assertEqual(claim["uri"], "/api/demo/comic-production/claim-report")
        self.assertEqual(claim["claim_level"], "demo_structure_only")
        self.assertEqual(claim["quality_claim"], "demo_structure_verified")
        self.assertTrue(claim["can_publicly_show"])
        self.assertFalse(claim["can_claim_real_quality"])
        self.assertEqual(claim["downstream_status"], "structure_demo_only")
        self.assertGreaterEqual(len(claim["claim_upgrade_checklist"]), 3)
        self.assertTrue(any(item["id"] == "run_real_models" for item in claim["claim_upgrade_checklist"]))
        self.assertTrue(all(item["required_evidence"] for item in claim["claim_upgrade_checklist"]))
        self.assertIn("不能宣称真实模型画质已验证", "\n".join(claim["forbidden_public_claims"]))
        self.assertEqual(claim["evidence"]["manifest_uri"], "/api/demo/comic-production/files/handoff_manifest.json")
        self.assertNotIn("E:\\", json.dumps(claim, ensure_ascii=False))
        research_claim_response = client.get("/api/demo/research/claim-report")
        self.assertEqual(research_claim_response.status_code, 200)
        research_claim = research_claim_response.json()
        self.assertEqual(research_claim["claim_level"], "staged_research_demo")
        self.assertFalse(research_claim["can_claim_full_automation"])
        self.assertIn("自动登录飞瓜", "\n".join(research_claim["forbidden_public_claims"]))
        upgrade_path = embed["quality_upgrade_path"]
        self.assertEqual(upgrade_path["current_public_level"], "demo_structure_only")
        self.assertEqual(upgrade_path["current_image_evidence"], "fixture_only")
        self.assertFalse(upgrade_path["can_claim_real_quality"])
        self.assertEqual(upgrade_path["recovery_action"], "regenerate_images")
        self.assertEqual(upgrade_path["trace_endpoint"], "/api/tasks/{task_id}/comic-v2-trace.json")
        self.assertIn("prompt_package", upgrade_path["preserves"])
        self.assertIn("image_production_evidence", upgrade_path["rebuilds"])
        self.assertEqual([item["order"] for item in upgrade_path["steps"]], [1, 2, 3])
        self.assertTrue(all(item["owner"] and item["action"] and item["evidence"] and item["expected"] for item in upgrade_path["steps"]))
        handoff_guide = next(
            item for item in embed["deliverable_reading_guide"] if "handoff manifest" in item["title"]
        )
        self.assertIn("quality_benchmark", handoff_guide["look_for"])
        self.assertIn("结构演示", handoff_guide["proves"])
        for item in embed["sample_deliverables"]:
            self.assertTrue(item["reader_guidance"])
            self.assertGreaterEqual(len(item["acceptance_signals"]), 3)
        self.assertTrue(
            any(
                "资产 ID" in " ".join(item["acceptance_signals"])
                for item in embed["sample_deliverables"]
            )
        )
        interview_script = embed["interview_demo_script"]
        self.assertEqual([item["order"] for item in interview_script], [1, 2, 3, 4])
        for item in interview_script:
            self.assertTrue(item["visitor_action"])
            self.assertTrue(item["product_response"])
            self.assertTrue(item["proof"])
            self.assertTrue(item["boundary"])
        script_text = "\n".join(
            item["visitor_action"] + item["product_response"] + item["proof"] + item["boundary"]
            for item in interview_script
        )
        self.assertIn("API Key", script_text)
        self.assertIn("demo-only", script_text)

        reproducibility = embed["reproducibility_checklist"]
        self.assertEqual([item["order"] for item in reproducibility], [1, 2, 3, 4, 5])
        self.assertIn("6 个下载物", reproducibility[2]["expected"])
        self.assertIn("7 个可复核文件", reproducibility[2]["expected"])
        self.assertIn("6/6 阅读指南", reproducibility[2]["expected"])
        for item in reproducibility:
            self.assertTrue(item["command"])
            self.assertTrue(item["expected"])
            self.assertTrue(item["if_fails"])
        repro_commands = "\n".join(item["command"] for item in reproducibility)
        self.assertIn("verify_public_demo_mode.py", repro_commands)
        self.assertIn("verify_static_public_showcase.py", repro_commands)
        self.assertIn("verify_release_readiness.py", repro_commands)
        post_run_validation = embed["post_run_validation"]
        self.assertEqual([item["order"] for item in post_run_validation], [1, 2, 3])
        post_run_text = json.dumps(post_run_validation, ensure_ascii=False)
        self.assertIn("交付物清点", post_run_text)
        self.assertIn("audit_comic_v2_handoffs.py", post_run_text)
        self.assertIn("verify_comic_real_production_claim.py", post_run_text)
        self.assertIn("verify_comic_v2_production_benchmark.py", post_run_text)
        self.assertIn("can_claim_real_quality=True", post_run_text)
        self.assertIn("production_quality_verified", post_run_text)
        self.assertTrue(all(item["command"] and item["expected"] and item["if_fails"] for item in post_run_validation))
        integration = embed["portfolio_integration"]
        self.assertEqual(integration["recommended_path"], "static_export")
        self.assertEqual(integration["static_export"]["source_dir"], "dist/public-showcase")
        self.assertEqual(integration["static_export"]["entrypoint"], "dist/public-showcase/index.html")
        self.assertFalse(integration["static_export"]["requires_backend"])
        self.assertFalse(integration["static_export"]["requires_api_key"])
        self.assertEqual(
            {item["id"] for item in integration["integration_options"]},
            {"standalone_static_site", "personal_site_subdirectory"},
        )
        self.assertIn("public/three-stooges/", json.dumps(integration["integration_options"], ensure_ascii=False))
        self.assertIn("API Key", " ".join(integration["must_not_include"]))
        self.assertIn("output/", " ".join(integration["must_not_include"]))
        self.assertIn("verify_release_readiness.py", "\n".join(integration["verification_commands"]))
        self.assertIn("check_no_secrets.py", "\n".join(payload["verification_commands"]))
        extension_story = embed["office_extension_story"]
        self.assertEqual(extension_story["starter_checklist_doc"], "docs/NEW_OFFICE_STARTER_CHECKLIST.md")
        self.assertEqual(extension_story["starter_item_count"], 8)
        self.assertEqual(len(extension_story["starter_checklist"]), 8)
        self.assertEqual(
            set(extension_story["starter_phases"]),
            {"product", "safety", "isolation", "workflow", "demo", "quality", "public_demo", "release"},
        )
        self.assertTrue(all(item["question"] and item["evidence"] for item in extension_story["starter_checklist"]))
        self.assertIn("verify_office_extension_governance.py", "\n".join(extension_story["required_verifiers"]))
        self.assertIn("API keys", extension_story["public_boundary"])
        candidate_ids = {item["id"] for item in extension_story["future_office_candidates"]}
        self.assertEqual(
            candidate_ids,
            {"short_video_ads", "ecommerce_selection", "story_ip", "technical_project"},
        )
        self.assertTrue(all(item["not_ready_reason"] for item in extension_story["future_office_candidates"]))
        backlog_ids = {item["id"] for item in extension_story["future_platform_backlog"]}
        self.assertEqual(backlog_ids, {"future_schema_validators", "future_recovery_events"})

        public_deployment = payload["public_deployment"]
        self.assertEqual(public_deployment["mode"], "demo_only")
        self.assertFalse(public_deployment["allows_real_model_calls"])
        self.assertFalse(public_deployment["allows_workspace_writes"])
        self.assertEqual(public_deployment["allowed_route_prefixes"], ["/api/demo"])
        static_export = public_deployment["static_export"]
        self.assertEqual(static_export["command"], "python scripts/export_public_showcase.py")
        self.assertEqual(static_export["entrypoint"], "dist/public-showcase/index.html")
        self.assertFalse(static_export["requires_backend"])
        self.assertFalse(static_export["requires_api_key"])
        self.assertIn("config.yaml", " ".join(public_deployment["forbidden_public_assets"]))
        self.assertIn(
            "python scripts/verify_static_public_showcase.py --format markdown",
            payload["verification_commands"],
        )
        self.assertIn(
            "python scripts/verify_comic_v2_downstream_handoff.py --format markdown",
            payload["verification_commands"],
        )

    def test_public_showcase_manifest_download_links_are_real(self):
        client = TestClient(app)
        payload = client.get("/api/demo/public-showcase").json()

        for demo in payload["featured_demos"]:
            for item in demo["downloads"]:
                response = client.get(item["uri"])
                self.assertEqual(response.status_code, 200)
                self.assertGreater(len(response.content), 20)

        claim_response = client.get(payload["portfolio_embed"]["real_production_claim"]["uri"])
        self.assertEqual(claim_response.status_code, 200)
        claim = claim_response.json()
        self.assertEqual(claim["claim_level"], "demo_structure_only")
        self.assertFalse(claim["can_claim_real_quality"])
        self.assertGreaterEqual(len(claim["claim_upgrade_checklist"]), 3)
        self.assertTrue(any(item["id"] == "run_real_models" for item in claim["claim_upgrade_checklist"]))
        self.assertNotIn("E:\\", json.dumps(claim, ensure_ascii=False))

    def test_favicon_request_does_not_create_browser_console_noise(self):
        client = TestClient(app)
        response = client.get("/favicon.ico")

        self.assertEqual(response.status_code, 204)



    def test_comic_demo_delivery_generation_uses_cross_process_lock(self):
        source = Path("src/web/app.py").read_text(encoding="utf-8")

        self.assertIn("def _demo_delivery_lock", source)
        self.assertIn("demo_delivery.lock", source)
        self.assertIn("with _demo_delivery_lock", source)

if __name__ == "__main__":
    unittest.main()
