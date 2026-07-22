import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.export_public_showcase import export_public_showcase


class StaticPublicShowcaseTests(unittest.TestCase):
    def setUp(self):
        Path("dist").mkdir(exist_ok=True)
        self.output_dir = Path(tempfile.mkdtemp(prefix=".test-public-showcase-", dir="dist"))

    def tearDown(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    def test_export_is_backend_free_and_contains_real_downloads(self):
        summary = export_public_showcase(self.output_dir)

        self.assertEqual(summary["status"], "passed")
        self.assertFalse(summary["requires_backend"])
        self.assertFalse(summary["requires_api_key"])
        self.assertFalse(summary["calls_real_models"])
        self.assertEqual(summary["download_count"], 6)

        manifest = json.loads((self.output_dir / "export-manifest.json").read_text(encoding="utf-8"))
        deploy_manifest = json.loads((self.output_dir / "portfolio-deploy-manifest.json").read_text(encoding="utf-8"))
        showcase = json.loads((self.output_dir / "showcase.json").read_text(encoding="utf-8"))
        index_text = (self.output_dir / "index.html").read_text(encoding="utf-8")
        self.assertEqual(showcase["mode"], "public_no_key_static_showcase")
        self.assertIn('<link rel="icon" href="data:,">', index_text)
        self.assertFalse(showcase["static_export"]["requires_backend"])
        self.assertEqual(showcase["static_export"]["reviewable_file_count"], 7)
        catalog = showcase["download_catalog"]
        self.assertEqual(len(catalog), 7)
        self.assertIn("data/comic_production_claim_report.json", {item["local_uri"] for item in catalog})
        self.assertIn("downloads/comic-production/handoff-inventory.json", {item["local_uri"] for item in catalog})
        self.assertIn("downloads/research/claim-report.json", {item["local_uri"] for item in catalog})
        self.assertTrue(all(item["title"] and item["sha256"] and item["bytes"] for item in catalog))
        self.assertTrue(all(item["proves"] or item["reader_guidance"] or item["look_for"] for item in catalog))
        demos = {item["office_id"]: item for item in showcase["featured_demos"]}
        comic_benchmark = demos["comic_production"]["quality_benchmark"]
        self.assertEqual(comic_benchmark["status"], "demo_structure_verified")
        self.assertFalse(comic_benchmark["production_quality_verified"])
        prompt_quality = comic_benchmark["prompt_quality_summary"]
        self.assertEqual(prompt_quality["status"], "ready")
        self.assertEqual(prompt_quality["clean_asset_prompt_count"], 7)
        self.assertEqual(prompt_quality["asset_prompt_count"], 7)
        self.assertEqual(prompt_quality["director_prompt_count"], 2)
        self.assertEqual(prompt_quality["shot_prompt_count"], 2)
        self.assertEqual(prompt_quality["issue_count"], 0)
        self.assertIn("checks", prompt_quality)
        self.assertIn("人物和道具资产保持纯白或近白色干净背景", prompt_quality["checks"])
        self.assertIn("负面提示词单独成段，并用“禁止”表达", prompt_quality["checks"])
        claim = showcase["portfolio_embed"]["real_production_claim"]
        self.assertEqual(claim["uri"], "data/comic_production_claim_report.json")
        self.assertEqual(claim["claim_level"], "demo_structure_only")
        self.assertFalse(claim["can_claim_real_quality"])
        self.assertNotIn("E:\\", json.dumps(claim, ensure_ascii=False))
        claim_payload = json.loads((self.output_dir / claim["uri"]).read_text(encoding="utf-8"))
        self.assertEqual(claim_payload["claim_level"], "demo_structure_only")
        self.assertFalse(claim_payload["can_claim_real_quality"])
        self.assertFalse(claim_payload["calls_real_models"])
        self.assertFalse(claim_payload["requires_api_key"])
        self.assertGreaterEqual(len(claim_payload["claim_upgrade_checklist"]), 3)
        self.assertTrue(all(item["required_evidence"] for item in claim_payload["claim_upgrade_checklist"]))
        self.assertEqual(claim_payload["claim_upgrade_recovery"]["recovery_action"], "regenerate_images")
        self.assertTrue(claim_payload["claim_upgrade_recovery"]["required"])
        self.assertIn("prompt_package", claim_payload["claim_upgrade_recovery"]["preserves"])
        self.assertIn("visual_review", claim_payload["claim_upgrade_recovery"]["rebuilds"])
        self.assertNotIn("E:\\", json.dumps(claim_payload, ensure_ascii=False))
        research_claim = showcase["portfolio_embed"]["research_claim_boundary"]
        self.assertEqual(research_claim["uri"], "downloads/research/claim-report.json")
        self.assertEqual(research_claim["claim_level"], "staged_research_demo")
        self.assertFalse(research_claim["can_claim_full_automation"])
        self.assertFalse(research_claim["requires_api_key"])
        self.assertFalse(research_claim["calls_real_models"])
        self.assertGreaterEqual(research_claim["evidence_handoff_count"], 3)
        self.assertEqual(research_claim["evidence_capture_playbook"]["status"], "human_account_required")
        self.assertGreaterEqual(research_claim["evidence_capture_playbook"]["step_count"], 5)
        self.assertIn("evidence_", research_claim["evidence_capture_playbook"]["file_naming_rule"])
        research_claim_payload = json.loads((self.output_dir / research_claim["uri"]).read_text(encoding="utf-8"))
        self.assertEqual(research_claim_payload["claim_level"], "staged_research_demo")
        self.assertFalse(research_claim_payload["can_claim_full_automation"])
        self.assertFalse(research_claim_payload["calls_real_models"])
        self.assertFalse(research_claim_payload["requires_api_key"])
        self.assertGreaterEqual(len(research_claim_payload["claim_upgrade_checklist"]), 3)
        self.assertGreaterEqual(len(research_claim_payload["evidence_handoff"]), 3)
        self.assertGreaterEqual(len(research_claim_payload["evidence_capture_playbook"]["steps"]), 5)
        self.assertNotIn("E:\\", json.dumps(research_claim_payload, ensure_ascii=False))
        upgrade_path = showcase["portfolio_embed"]["quality_upgrade_path"]
        self.assertEqual(upgrade_path["current_public_level"], "demo_structure_only")
        self.assertEqual(upgrade_path["current_image_evidence"], "fixture_only")
        self.assertEqual(upgrade_path["recovery_action"], "regenerate_images")
        self.assertEqual(upgrade_path["trace_endpoint"], "/api/tasks/{task_id}/comic-v2-trace.json")
        self.assertEqual(len(upgrade_path["steps"]), 3)
        script_text = "\n".join(
            item["product_response"] for item in showcase["portfolio_embed"]["interview_demo_script"]
        )
        self.assertIn("访客打开页面时只读取随包的 data.js", script_text)
        self.assertIn("六份交付物已经随静态站点一起导出", script_text)
        fast_review = showcase["portfolio_embed"]["fast_review_route"]
        self.assertEqual([item["order"] for item in fast_review], [1, 2, 3, 4])
        self.assertTrue(all(item["viewer_action"] and item["proof"] and item["next_anchor"] for item in fast_review))
        repro = showcase["portfolio_embed"]["reproducibility_checklist"]
        self.assertEqual(len(repro), 5)
        self.assertIn("6 个下载物", repro[2]["expected"])
        self.assertIn("7 个可复核文件", repro[2]["expected"])
        self.assertTrue(any("verify_release_readiness.py" in item["command"] for item in repro))
        self.assertTrue(all(item["expected"] and item["if_fails"] for item in repro))
        first_run_paths = {item["id"]: item for item in showcase["portfolio_embed"]["first_run_paths"]}
        self.assertEqual(set(first_run_paths), {"public_demo", "local_real_use", "developer_extension"})
        self.assertFalse(first_run_paths["public_demo"]["requires_api_key"])
        self.assertTrue(first_run_paths["local_real_use"]["requires_api_key"])
        self.assertIn("verify_public_demo_mode.py", first_run_paths["public_demo"]["verification"])
        self.assertIn("doctor.py", first_run_paths["local_real_use"]["verification"])
        self.assertIn("verify_office_extension_governance.py", first_run_paths["developer_extension"]["verification"])
        self.assertTrue(all(len(item["do_first"]) >= 3 for item in first_run_paths.values()))
        post_run = showcase["portfolio_embed"]["post_run_validation"]
        self.assertEqual([item["order"] for item in post_run], [1, 2, 3])
        post_run_text = json.dumps(post_run, ensure_ascii=False)
        self.assertIn("audit_comic_v2_handoffs.py", post_run_text)
        self.assertIn("verify_comic_real_production_claim.py", post_run_text)
        self.assertIn("verify_comic_v2_production_benchmark.py", post_run_text)
        self.assertIn("can_claim_real_quality=True", post_run_text)
        self.assertIn("production_quality_verified", post_run_text)
        self.assertTrue(all(item["expected"] and item["if_fails"] for item in post_run))
        integration = showcase["portfolio_embed"]["portfolio_integration"]
        self.assertEqual(integration["static_export"]["source_dir"], "dist/public-showcase")
        self.assertEqual(integration["static_export"]["entrypoint"], "dist/public-showcase/index.html")
        self.assertEqual(
            {item["id"] for item in integration["integration_options"]},
            {"standalone_static_site", "personal_site_subdirectory"},
        )
        self.assertIn("public/three-stooges/", json.dumps(integration["integration_options"], ensure_ascii=False))
        self.assertIn("config.yaml", " ".join(integration["must_not_include"]))
        extension_story = showcase["portfolio_embed"]["office_extension_story"]
        self.assertEqual(extension_story["starter_checklist_doc"], "docs/NEW_OFFICE_STARTER_CHECKLIST.md")
        self.assertEqual(extension_story["starter_item_count"], 8)
        self.assertEqual(len(extension_story["starter_checklist"]), 8)
        self.assertIn("isolation", extension_story["starter_phases"])
        self.assertIn("public_demo", extension_story["starter_phases"])
        self.assertIn("verify_office_extension_governance.py", "\n".join(extension_story["required_verifiers"]))
        candidate_ids = {item["id"] for item in extension_story["future_office_candidates"]}
        self.assertEqual(
            candidate_ids,
            {"short_video_ads", "ecommerce_selection", "story_ip", "technical_project"},
        )
        self.assertTrue(all(item["not_ready_reason"] for item in extension_story["future_office_candidates"]))
        backlog_ids = {item["id"] for item in extension_story["future_platform_backlog"]}
        self.assertEqual(backlog_ids, {"future_schema_validators", "future_recovery_events"})
        launch_matrix = showcase["portfolio_embed"]["office_launch_matrix"]
        self.assertEqual(launch_matrix["summary"]["office_count"], 3)
        self.assertEqual(launch_matrix["summary"]["primary_allowed_count"], 1)
        launch_by_office = {item["office_id"]: item for item in launch_matrix["offices"]}
        self.assertTrue(launch_by_office["comic_production"]["primary_allowed"])
        self.assertEqual(launch_by_office["comic"]["visitor_label"], "旧版兼容入口")
        self.assertIn("legacy_migration_required", launch_by_office["comic"]["blocked_by"])
        self.assertEqual(deploy_manifest["mode"], "public_no_key_portfolio_deploy")
        self.assertEqual(deploy_manifest["source_dir"], "dist/public-showcase")
        self.assertEqual(deploy_manifest["personal_site_target"], "public/three-stooges/")
        self.assertEqual(deploy_manifest["personal_site_url_path"], "/three-stooges/")
        self.assertEqual(deploy_manifest["live_url"], "https://www.atticus.asia/three-stooges/")
        self.assertFalse(deploy_manifest["requires_backend"])
        self.assertFalse(deploy_manifest["requires_api_key"])
        self.assertFalse(deploy_manifest["calls_real_models"])
        self.assertFalse(deploy_manifest["allows_workspace_writes"])
        live_verification = deploy_manifest["live_verification"]
        self.assertEqual(live_verification["status"], "external_required")
        self.assertEqual(live_verification["doctor_command"], "npm run doctor:deploy")
        self.assertEqual(live_verification["check_command"], "npm run check:online")
        self.assertEqual(live_verification["ship_command"], "npm run ship:vercel")
        self.assertTrue(live_verification["requires_vercel_authorization"])
        self.assertIn("check:online", live_verification["do_not_claim_live_until"])
        self.assertEqual(deploy_manifest["sample_download_count"], 6)
        self.assertIn("downloads/", deploy_manifest["required_files"])
        self.assertIn("config.yaml", " ".join(deploy_manifest["forbidden_public_assets"]))
        self.assertTrue(any("verify_static_public_showcase.py" in item for item in deploy_manifest["verification_commands"]))
        self.assertTrue(any("doctor:deploy" in item for item in deploy_manifest["operator_checklist"]))
        self.assertTrue(any("check:online" in item for item in deploy_manifest["operator_checklist"]))
        self.assertGreaterEqual(len(deploy_manifest["operator_checklist"]), 5)
        showcase_live_verification = showcase["public_deployment"]["live_verification"]
        self.assertEqual(showcase_live_verification["status"], "external_required")
        self.assertEqual(showcase_live_verification["doctor_command"], "npm run doctor:deploy")
        self.assertEqual(showcase_live_verification["check_command"], "npm run check:online")
        self.assertEqual(showcase_live_verification["live_url"], "https://www.atticus.asia/three-stooges/")
        quick_start = showcase["portfolio_embed"]["downstream_quick_start"]
        self.assertEqual([item["step"] for item in quick_start], [1, 2, 3, 4, 5])
        self.assertIn("逐镜头生成视频", json.dumps(quick_start, ensure_ascii=False))
        self.assertTrue(all(item["owner"] and item["acceptance"] for item in quick_start))
        asset_matrix = showcase["portfolio_embed"]["asset_requirement_matrix"]
        self.assertEqual(asset_matrix["manifest_uri"], "downloads/comic-production/files/handoff_manifest.json")
        self.assertEqual(asset_matrix["ready_assets"], asset_matrix["total_assets"])
        self.assertEqual(asset_matrix["missing_required_images"], 0)
        asset_matrix_text = json.dumps(asset_matrix, ensure_ascii=False)
        self.assertIn("three_view", asset_matrix_text)
        self.assertIn("expression_sheet", asset_matrix_text)
        self.assertIn("turnaround", asset_matrix_text)
        self.assertIn("top_down", asset_matrix_text)
        shot_contract = showcase["portfolio_embed"]["shot_contract"]
        self.assertEqual(shot_contract["manifest_uri"], "downloads/comic-production/files/handoff_manifest.json")
        contract_text = json.dumps(shot_contract, ensure_ascii=False)
        self.assertIn("first_frame_reference_image", contract_text)
        self.assertIn("reference_asset_chain", contract_text)
        self.assertIn("director_execution", contract_text)
        self.assertIn("verify_comic_v2_downstream_handoff.py", contract_text)
        badge = showcase["portfolio_embed"]["release_badge"]
        self.assertEqual(badge["status"], "safe_public_demo")
        self.assertEqual(badge["mode"], "demo_only")
        self.assertFalse(badge["can_claim_real_quality"])
        self.assertGreaterEqual(len(badge["signals"]), 5)
        self.assertIn("verify_release_readiness.py", badge["primary_gate"])
        safety_text = "\n".join(showcase["safety_boundaries"])
        self.assertIn("页面运行时不连接 FastAPI", safety_text)
        self.assertIn("真实生产声明报告", safety_text)
        self.assertGreater((self.output_dir / "assets" / "public-showcase-desktop.png").stat().st_size, 100_000)
        for item in manifest["downloads"]:
            self.assertFalse(item["local_uri"].startswith("/"))
            self.assertTrue(Path(item["local_uri"]).suffix, item["local_uri"])
            self.assertGreater((self.output_dir / item["local_uri"]).stat().st_size, 20)
        for item in catalog:
            self.assertTrue(Path(item["local_uri"]).suffix, item["local_uri"])
        for item in showcase["portfolio_embed"]["deliverable_reading_guide"]:
            self.assertTrue((self.output_dir / item["uri"]).is_file())
        static_script = (self.output_dir / "app.js").read_text(encoding="utf-8")
        index_text = (self.output_dir / "index.html").read_text(encoding="utf-8")
        style_text = (self.output_dir / "style.css").read_text(encoding="utf-8")
        self.assertIn("可复核文件目录", index_text)
        self.assertIn("最快验收路线", index_text)
        self.assertIn("未宣称真实画质", static_script)
        self.assertIn("claim.claim_upgrade_checklist", static_script)
        self.assertIn("claim.claim_upgrade_recovery", static_script)
        self.assertIn("portfolio.research_claim_boundary", static_script)
        self.assertIn("research-claim-card", static_script)
        self.assertIn("research-capture-playbook-card", static_script)
        self.assertIn("renderAssetRequirementMatrix", static_script)
        self.assertIn("asset_requirement_matrix", static_script)
        self.assertIn("资产图片规格矩阵", index_text)
        self.assertIn("research-capture-steps", static_script)
        self.assertIn("research-capture-playbook-card", style_text)
        self.assertIn("fast_review_route", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))
        self.assertIn("renderFastReviewRoute", static_script)
        self.assertIn("fast-review-item", style_text)
        self.assertIn("showcase.download_catalog", static_script)
        self.assertIn("renderDownloadCatalog", static_script)
        self.assertIn("catalog-card", style_text)
        self.assertIn("hash-code", style_text)
        self.assertIn("quality_upgrade_path", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))
        self.assertIn("renderQualityUpgradePath", static_script)
        self.assertIn("claim-upgrade-card", static_script)
        self.assertIn("claim-recovery-card", static_script)
        self.assertIn("claim-recovery-card", style_text)
        self.assertIn("claim-recovery-steps", style_text)
        self.assertIn("renderReleaseBadge", static_script)
        self.assertIn("renderDownstreamQuickStart", static_script)
        self.assertIn("renderShotContract", static_script)
        self.assertIn("shot_contract", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))
        self.assertIn("shot-contract-grid", style_text)
        self.assertIn("renderReproducibilityChecklist", static_script)
        self.assertIn("renderFirstRunPaths", static_script)
        self.assertIn("portfolio.first_run_paths", static_script)
        self.assertIn("first-run-paths", index_text)
        self.assertIn("first-run-grid", style_text)
        self.assertIn("真实产物验收", index_text)
        self.assertIn("renderPostRunValidation", static_script)
        self.assertIn("portfolio.post_run_validation", static_script)
        self.assertIn("portfolio.office_extension_story", static_script)
        self.assertIn("renderOfficeExtensionStory", static_script)
        self.assertIn("extension-check-grid", style_text)
        self.assertIn("portfolio.office_launch_matrix", static_script)
        self.assertIn("办公室公开状态", static_script)
        self.assertIn("launch-matrix-grid", style_text)
        self.assertIn("future_office_candidates", static_script)
        self.assertIn("future_platform_backlog", static_script)
        self.assertIn("prompt_quality_summary", static_script)
        self.assertIn("prompt-gate-checks", static_script)
        self.assertIn("提示词门禁", static_script)
        self.assertIn("prompt-gate-checks", style_text)
        self.assertIn("提示词问题", static_script)
        self.assertIn("renderPortfolioIntegration", static_script)
        self.assertIn("handoff_inventory", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))
        self.assertIn("portfolio_integration", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))

    def test_static_readiness_verifier_is_public_operator_readable(self):
        completed = subprocess.run(
            [sys.executable, "scripts/verify_static_public_showcase.py", "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Static Public Showcase Readiness", completed.stdout)
        self.assertIn("Status: `passed`", completed.stdout)
        self.assertIn("Downloadable deliverables: 6", completed.stdout)
        self.assertIn("Reviewable catalog: 7 files", completed.stdout)
        self.assertIn("Reading guide: 6/6", completed.stdout)
        self.assertIn("First-run paths: 3", completed.stdout)
        self.assertIn("Downstream quick-start: 5 steps", completed.stdout)
        self.assertIn("Shot contract: 4 fields", completed.stdout)
        self.assertIn("Reproducibility checklist: 5 commands", completed.stdout)
        self.assertIn("Real output validation: 3/3 steps", completed.stdout)
        self.assertIn("Release badge: safe_public_demo", completed.stdout)
        self.assertIn("Comic claim report: data/comic_production_claim_report.json / ready=True", completed.stdout)
        self.assertIn("Claim upgrade checklist: 3 items", completed.stdout)
        self.assertIn("Claim upgrade recovery: action=regenerate_images / steps=3", completed.stdout)
        self.assertIn("Quality upgrade path: action=regenerate_images / steps=3", completed.stdout)
        self.assertIn("Research claim report: downloads/research/claim-report.json / ready=True / level=staged_research_demo / full_automation=False", completed.stdout)
        self.assertIn("Research claim upgrade checklist: 3 items / evidence_handoff=3 / capture_steps=5", completed.stdout)
        self.assertIn("New office extension: checklist=8 / phases=8 / doc=docs/NEW_OFFICE_STARTER_CHECKLIST.md", completed.stdout)
        self.assertIn("Future office candidates: 4 / backlog=2", completed.stdout)
        self.assertIn("Office launch matrix: public_ready=2/3 / primary=1 / legacy=1", completed.stdout)
        self.assertIn("Prompt quality: ready / assets=7/7 / directors=2/2 / issues=0", completed.stdout)
        self.assertIn("Portfolio integration: source=dist/public-showcase / options=2", completed.stdout)
        self.assertIn("Portfolio deploy manifest: portfolio-deploy-manifest.json / target=public/three-stooges/", completed.stdout)
        self.assertIn("Portfolio live verification: external_required / url=https://www.atticus.asia/three-stooges/ / check=npm run check:online", completed.stdout)
        self.assertIn("Requires backend: False", completed.stdout)

    def test_static_readiness_verifier_can_check_existing_export(self):
        export_public_showcase(self.output_dir)

        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_static_public_showcase.py",
                "--format",
                "markdown",
                "--existing-dir",
                str(self.output_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Status: `passed`", completed.stdout)
        self.assertIn("Verification source: `existing_dir`", completed.stdout)
        self.assertIn("Future office candidates: 4 / backlog=2", completed.stdout)
        self.assertIn("Requires API Key: False", completed.stdout)


if __name__ == "__main__":
    unittest.main()
