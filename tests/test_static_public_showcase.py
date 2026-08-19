import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.export_public_showcase import export_public_showcase
from scripts.verify_public_showcase_live import verify_public_showcase_live


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
        self.assertEqual(summary["download_count"], 7)
        self.assertEqual(summary["text_integrity_status"], "passed")
        self.assertGreaterEqual(summary["text_integrity_scanned_files"], 10)
        self.assertEqual(summary["text_integrity_findings"], [])

        manifest = json.loads((self.output_dir / "export-manifest.json").read_text(encoding="utf-8"))
        deploy_manifest = json.loads((self.output_dir / "portfolio-deploy-manifest.json").read_text(encoding="utf-8"))
        showcase = json.loads((self.output_dir / "showcase.json").read_text(encoding="utf-8"))
        visitor_guide = json.loads((self.output_dir / "data" / "visitor_acceptance_guide.json").read_text(encoding="utf-8"))
        index_text = (self.output_dir / "index.html").read_text(encoding="utf-8")
        self.assertEqual(showcase["mode"], "public_no_key_static_showcase")
        self.assertIn('<link rel="icon" href="data:,">', index_text)
        self.assertFalse(showcase["static_export"]["requires_backend"])
        self.assertEqual(showcase["visitor_acceptance_guide"]["uri"], "data/visitor_acceptance_guide.json")
        self.assertEqual(showcase["visitor_acceptance_guide"]["step_count"], 7)
        self.assertEqual(showcase["visitor_acceptance_guide"]["download_count"], 8)
        self.assertEqual(showcase["visitor_acceptance_guide"]["live_verification_status"], "external_required")
        self.assertEqual(visitor_guide["mode"], "public_no_key_visitor_acceptance")
        self.assertFalse(visitor_guide["requires_backend"])
        self.assertFalse(visitor_guide["requires_api_key"])
        self.assertFalse(visitor_guide["calls_real_models"])
        self.assertEqual(len(visitor_guide["visitor_route"]), 7)
        self.assertEqual(len(visitor_guide["download_acceptance"]), 8)
        self.assertEqual(visitor_guide["live_verification"]["check_command"], "npm run check:online")
        self.assertIn("check:online", visitor_guide["live_verification"]["do_not_claim_live_until"])
        visitor_guide_text = json.dumps(visitor_guide, ensure_ascii=False)
        self.assertIn("config.yaml", visitor_guide_text)
        self.assertIn("API Key", visitor_guide_text)
        self.assertIn("user_data/", visitor_guide_text)
        self.assertEqual(showcase["static_export"]["reviewable_file_count"], 8)
        catalog = showcase["download_catalog"]
        self.assertEqual(len(catalog), 8)
        self.assertIn("data/comic_production_claim_report.json", {item["local_uri"] for item in catalog})
        self.assertIn("downloads/comic-production/files/trace.json", {item["local_uri"] for item in catalog})
        self.assertIn("downloads/comic-production/handoff-inventory.json", {item["local_uri"] for item in catalog})
        self.assertIn("downloads/research/claim-report.json", {item["local_uri"] for item in catalog})
        self.assertTrue(all(item["title"] and item["sha256"] and item["bytes"] for item in catalog))
        self.assertTrue(all(item["proves"] or item["reader_guidance"] or item["look_for"] for item in catalog))
        handoff_inventory = json.loads(
            (self.output_dir / "downloads/comic-production/handoff-inventory.json").read_text(encoding="utf-8")
        )
        self.assertFalse(handoff_inventory["requires_api_key"])
        self.assertFalse(handoff_inventory["calls_real_models"])
        self.assertEqual(handoff_inventory["production_verified_count"], 0)
        demo_recoveries = [
            item["recommended_recovery"]
            for item in handoff_inventory["items"]
            if item["quality_claim"] == "demo_structure_verified"
        ]
        self.assertTrue(demo_recoveries)
        self.assertTrue(all(item["action"] == "regenerate_images" for item in demo_recoveries))
        self.assertTrue(all(item["expected_stage"] == "image_generation" for item in demo_recoveries))
        self.assertTrue(all("story_contract" in item["preserves"] for item in demo_recoveries))
        self.assertTrue(all("fixture_images" in item["clears"] for item in demo_recoveries))
        image_totals = {
            "total": sum(item["total_images"] for item in handoff_inventory["items"]),
            "usable": sum(item["usable_images"] for item in handoff_inventory["items"]),
            "rework": sum(item["waste_or_rework_images"] for item in handoff_inventory["items"]),
        }
        self.assertEqual(image_totals["total"], len(handoff_inventory["items"]) * 7)
        self.assertEqual(image_totals["usable"], image_totals["total"])
        self.assertEqual(image_totals["rework"], 0)
        demo_items = [
            item
            for item in handoff_inventory["items"]
            if item["quality_claim"] == "demo_structure_verified"
        ]
        self.assertTrue(demo_items)
        self.assertTrue(all(item["usable_images"] == 7 for item in demo_items))
        self.assertTrue(all(item["waste_or_rework_images"] == 0 for item in demo_items))
        self.assertTrue(all("image_quality_summary" in item for item in demo_items))
        self.assertTrue(all(isinstance(item["failed_image_ids"], list) for item in demo_items))
        self.assertTrue(all(isinstance(item["rework_action_summary"], list) for item in demo_items))
        rework_cards = [
            instruction
            for item in demo_items
            for instruction in item["image_quality_summary"].get("rework_instructions", [])
        ]
        self.assertEqual(rework_cards, [])
        demos = {item["office_id"]: item for item in showcase["featured_demos"]}
        comic_benchmark = demos["comic_production"]["quality_benchmark"]
        self.assertEqual(comic_benchmark["status"], "demo_structure_verified")
        self.assertFalse(comic_benchmark["production_quality_verified"])
        image_quality = comic_benchmark["image_quality_summary"]
        self.assertEqual(image_quality["total_images"], 7)
        self.assertEqual(image_quality["usable_images"], 7)
        self.assertEqual(image_quality["waste_or_rework_images"], 0)
        self.assertEqual(image_quality["waste_or_rework_rate"], 0)
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
        gate = claim_payload["real_quality_promotion_gate"]
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["status"], "evidence_missing")
        self.assertIn("visual_evidence_model_reviewed", gate["missing_check_ids"])
        self.assertIn("production_quality_verified", gate["missing_check_ids"])
        self.assertGreaterEqual(len(gate["checks"]), 6)
        real_model_evidence = claim_payload["real_model_evidence_requirements"]
        self.assertEqual(real_model_evidence["status"], "evidence_missing")
        self.assertFalse(real_model_evidence["ready_for_real_quality_claim"])
        self.assertIn("non_fixture_images", real_model_evidence["missing_check_ids"])
        self.assertIn("provider_model_bound", real_model_evidence["missing_check_ids"])
        self.assertNotIn("seven_dimension_scores", real_model_evidence["missing_check_ids"])
        self.assertEqual(real_model_evidence["seven_dimension_scored_reviews"], 7)
        self.assertGreaterEqual(len(real_model_evidence["checks"]), 6)
        self.assertGreaterEqual(len(claim_payload["claim_upgrade_checklist"]), 3)
        self.assertTrue(all(item["required_evidence"] for item in claim_payload["claim_upgrade_checklist"]))
        self.assertEqual(claim_payload["claim_upgrade_recovery"]["recovery_action"], "regenerate_images")
        self.assertTrue(claim_payload["claim_upgrade_recovery"]["required"])
        self.assertIn("prompt_package", claim_payload["claim_upgrade_recovery"]["preserves"])
        self.assertIn("visual_review", claim_payload["claim_upgrade_recovery"]["rebuilds"])
        decision = claim_payload["downstream_handoff_decision"]
        self.assertEqual(decision["status"], "structure_demo_only")
        self.assertFalse(decision["handoff_allowed"])
        self.assertIn("不能交给下游", decision["decision"])
        self.assertIn("真实模型生成的非 fixture 图片", decision["missing_before_handoff"])
        self.assertIn("regenerate_images", "\n".join(decision["required_actions"]))
        self.assertNotIn("E:\\", json.dumps(claim_payload, ensure_ascii=False))
        research_claim = showcase["portfolio_embed"]["research_claim_boundary"]
        self.assertEqual(research_claim["uri"], "downloads/research/claim-report.json")
        self.assertEqual(research_claim["claim_level"], "staged_research_demo")
        self.assertFalse(research_claim["can_claim_full_automation"])
        self.assertFalse(research_claim["requires_api_key"])
        self.assertFalse(research_claim["calls_real_models"])
        self.assertGreaterEqual(research_claim["evidence_handoff_count"], 3)
        self.assertGreaterEqual(len(research_claim["evidence_handoff"]), 3)
        research_requirements = research_claim["research_evidence_requirements"]
        self.assertEqual(research_requirements["status"], "staged_only")
        self.assertFalse(research_requirements["ready_for_final_research_claim"])
        self.assertIn("pending_evidence_disclosed", research_requirements["blocking_check_ids"])
        self.assertIn("placeholder_sources_disclosed", research_requirements["blocking_check_ids"])
        self.assertIn("final_report_not_claimed", research_requirements["blocking_check_ids"])
        first_handoff = research_claim["evidence_handoff"][0]
        self.assertTrue(first_handoff["target_evidence"])
        self.assertTrue(first_handoff["why_needed"])
        self.assertTrue(first_handoff["upgrades"])
        self.assertEqual(first_handoff["priority"], "P0")
        self.assertIn("evidence_01", first_handoff["suggested_file_name"])
        self.assertIn("截图", first_handoff["acceptance"])
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
        self.assertEqual(research_claim_payload["research_evidence_requirements"]["status"], "staged_only")
        self.assertNotIn("E:\\", json.dumps(research_claim_payload, ensure_ascii=False))
        upgrade_path = showcase["portfolio_embed"]["quality_upgrade_path"]
        self.assertEqual(upgrade_path["current_public_level"], "demo_structure_only")
        self.assertEqual(upgrade_path["current_image_evidence"], "fixture_only")
        self.assertEqual(upgrade_path["recovery_action"], "regenerate_images")
        self.assertEqual(upgrade_path["trace_endpoint"], "/api/tasks/{task_id}/comic-v2-trace.json")
        self.assertEqual(len(upgrade_path["steps"]), 3)
        real_upgrade = showcase["portfolio_embed"]["real_quality_upgrade_plan"]
        self.assertEqual(real_upgrade["current_claim_level"], "demo_structure_only")
        self.assertEqual(real_upgrade["target_claim_level"], "real_quality_verified")
        self.assertEqual(real_upgrade["upgrade_status"], "blocked_until_real_model_evidence")
        self.assertEqual(real_upgrade["recovery_action"], "regenerate_images")
        self.assertEqual(len(real_upgrade["operator_steps"]), 5)
        self.assertEqual(
            {item["department_id"] for item in real_upgrade["model_preflight_departments"]},
            {"gongbu", "xingbu", "bingbu"},
        )
        self.assertFalse(real_upgrade["evidence_contract"]["ready_for_real_quality_claim"])
        self.assertIn("provider_model_bound", real_upgrade["evidence_contract"]["missing_check_ids"])
        recovery_drill = showcase["portfolio_embed"]["public_recovery_drill"]
        self.assertEqual(recovery_drill["current_evidence_level"], "fixture_only")
        self.assertEqual(recovery_drill["recommended_action"], "regenerate_images")
        self.assertEqual(recovery_drill["recovery_endpoint"], "/api/workspaces/{workspace_id}/comic/v2/quality/recover")
        self.assertEqual(len(recovery_drill["operator_steps"]), 4)
        self.assertIn("旧 Word 画布", " ".join(recovery_drill["preserve_policy"]))
        self.assertIn("视觉质检", " ".join(recovery_drill["clear_policy"]))
        self.assertIn("model_reviewed", " ".join(recovery_drill["acceptance"]))
        script_text = "\n".join(
            item["product_response"] for item in showcase["portfolio_embed"]["interview_demo_script"]
        )
        self.assertIn("访客打开页面时只读取随包的 data.js", script_text)
        self.assertIn("七份公开下载物已经随静态站点一起导出", script_text)
        fast_review = showcase["portfolio_embed"]["fast_review_route"]
        self.assertEqual([item["order"] for item in fast_review], [1, 2, 3, 4, 5])
        fast_review_text = json.dumps(fast_review, ensure_ascii=False)
        self.assertIn("asset-matrix-title", fast_review_text)
        self.assertIn("three_view", fast_review_text)
        self.assertIn("clean_background_required", fast_review_text)
        self.assertTrue(all(item["viewer_action"] and item["proof"] and item["next_anchor"] for item in fast_review))
        repro = showcase["portfolio_embed"]["reproducibility_checklist"]
        self.assertEqual(len(repro), 5)
        self.assertIn("7 个下载物", repro[2]["expected"])
        self.assertIn("8 个可复核文件", repro[2]["expected"])
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
        first_run_guide = showcase["portfolio_embed"]["first_run_guide"]
        self.assertEqual(first_run_guide["mode"], "guided_first_run")
        self.assertEqual(len(first_run_guide["quick_checks"]), 5)
        self.assertFalse(first_run_guide["requires_model_credentials"])
        self.assertFalse(first_run_guide["calls_real_models"])
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
        ci_proof = integration["portfolio_ci_proof"]
        self.assertEqual(ci_proof["status"], "repo_static_checks")
        self.assertEqual(ci_proof["workflow_path"], ".github/workflows/three-cobblers-showcase.yml")
        self.assertIn("npm run check:showcase", ci_proof["commands"])
        self.assertIn("npm run check:deploy-handoff", ci_proof["commands"])
        self.assertIn("npm run build", ci_proof["commands"])
        self.assertEqual(ci_proof["live_authority"], "npm run check:online")
        self.assertIn("Vercel production route", " ".join(ci_proof["does_not_prove"]))
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
        self.assertEqual(
            [
                item["id"]
                for item in sorted(
                    extension_story["future_office_candidates"],
                    key=lambda item: item["priority_rank"],
                )
            ],
            ["ecommerce_selection", "short_video_ads", "story_ip", "technical_project"],
        )
        self.assertEqual(
            [item["office_id"] for item in extension_story["future_office_prioritization"]["recommended_order"]],
            ["ecommerce_selection", "short_video_ads", "story_ip", "technical_project"],
        )
        self.assertIn("复用现有证据链", extension_story["future_office_prioritization"]["decision_rule"])
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
        deploy_ci = deploy_manifest["ci_verification"]
        self.assertEqual(deploy_ci["status"], "repo_static_checks")
        self.assertEqual(deploy_ci["workflow_path"], ".github/workflows/three-cobblers-showcase.yml")
        self.assertIn("npm run check:showcase", deploy_ci["commands"])
        self.assertIn("npm run check:deploy-handoff", deploy_ci["commands"])
        self.assertIn("npm run build", deploy_ci["commands"])
        self.assertEqual(deploy_ci["live_authority"], "npm run check:online")
        self.assertIn("real model calls", " ".join(deploy_ci["does_not_prove"]))
        self.assertEqual(deploy_manifest["sample_download_count"], 7)
        self.assertIn("downloads/", deploy_manifest["required_files"])
        self.assertIn("data/visitor_acceptance_guide.json", deploy_manifest["required_files"])
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
        showcase_ci = showcase["public_deployment"]["ci_verification"]
        self.assertEqual(showcase_ci["workflow_path"], ".github/workflows/three-cobblers-showcase.yml")
        self.assertEqual(showcase_ci["live_authority"], "npm run check:online")
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
        asset_spec = showcase["portfolio_embed"]["asset_image_production_spec"]
        asset_usage_map = showcase["portfolio_embed"]["asset_usage_map"]
        self.assertEqual(asset_usage_map["manifest_uri"], "downloads/comic-production/files/handoff_manifest.json")
        self.assertEqual(asset_usage_map["ready_assets"], asset_usage_map["total_assets"])
        self.assertGreaterEqual(asset_usage_map["image_roles"], asset_matrix["total_assets"])
        asset_usage_text = json.dumps(asset_usage_map, ensure_ascii=False)
        self.assertIn("identity_baseline_image_id", asset_usage_text)
        self.assertIn("referenced_by_shots", asset_usage_text)
        self.assertIn("downstream_instruction", asset_usage_text)
        self.assertIn("三视图", asset_usage_text)
        self.assertEqual(
            {item["asset_type"] for item in asset_spec["asset_types"]},
            {"character", "prop", "scene"},
        )
        asset_spec_text = json.dumps(asset_spec, ensure_ascii=False)
        self.assertIn("clean_white_or_near_white_background", asset_spec_text)
        self.assertIn("spatial_environment_not_white_background", asset_spec_text)
        self.assertIn("不要把人物放进完整剧情场面", asset_spec_text)
        self.assertIn("不要把场景做成白底静物", asset_spec_text)
        self.assertIn("verify_comic_v2_downstream_handoff.py", asset_spec_text)
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
        self.assertIn("real_quality_promotion_gate", static_script)
        self.assertIn("public-claim-promotion-gate", static_script)
        self.assertIn("portfolio.research_claim_boundary", static_script)
        self.assertIn("research-claim-card", static_script)
        self.assertIn("research-capture-playbook-card", static_script)
        self.assertIn("renderAssetRequirementMatrix", static_script)
        self.assertIn("asset_requirement_matrix", static_script)
        self.assertIn("renderAssetUsageMap", static_script)
        self.assertIn("asset_usage_map", static_script)
        self.assertIn("asset-usage-map", index_text)
        self.assertIn("asset-usage-card", style_text)
        self.assertIn("renderAssetProductionSpec", static_script)
        self.assertIn("asset_image_production_spec", static_script)
        self.assertIn("asset-spec-grid", index_text)
        self.assertIn("asset-spec-card", style_text)
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
        self.assertIn("real_quality_upgrade_plan", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))
        self.assertIn("renderRealQualityUpgradePlan", static_script)
        self.assertIn("real-quality-upgrade-plan-card", static_script)
        self.assertIn("real-quality-model-grid", style_text)
        self.assertIn("renderQualityUpgradePath", static_script)
        self.assertIn("claim-upgrade-card", static_script)
        self.assertIn("claim-recovery-card", static_script)
        self.assertIn("claim-recovery-card", style_text)
        self.assertIn("claim-recovery-steps", style_text)
        self.assertIn("public_recovery_drill", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))
        self.assertIn("renderPublicRecoveryDrill", static_script)
        self.assertIn("public-recovery-drill-card", style_text)
        self.assertIn("public-recovery-policy-grid", style_text)
        self.assertIn("renderImageReworkSummary", static_script)
        self.assertIn("image-rework-summary", static_script)
        self.assertIn("image-rework-summary", style_text)
        self.assertIn("rework_action_summary", static_script)
        self.assertIn("researchClaim.evidence_handoff", static_script)
        self.assertIn("suggested_file_name", static_script)
        self.assertIn("handoff-acceptance", static_script)
        self.assertIn("research-evidence-handoff-card", static_script)
        self.assertIn("research-evidence-handoff-card", style_text)
        self.assertIn("research-evidence-handoff-item", style_text)
        self.assertIn("handoff-acceptance", style_text)
        self.assertIn("renderReleaseBadge", static_script)
        self.assertIn("renderDownstreamQuickStart", static_script)
        self.assertIn("renderShotContract", static_script)
        self.assertIn("shot_contract", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))
        self.assertIn("shot-contract-grid", style_text)
        self.assertIn("renderReproducibilityChecklist", static_script)
        self.assertIn("renderFirstRunPaths", static_script)
        self.assertIn("portfolio.first_run_paths", static_script)
        self.assertIn("renderFirstRunGuideChecks", static_script)
        self.assertIn("portfolio.first_run_guide", static_script)
        self.assertIn("first-run-paths", index_text)
        self.assertIn("first-run-guide-checks", index_text)
        self.assertIn("first-run-grid", style_text)
        self.assertIn("first-run-command-list", style_text)
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
        self.assertIn("future_office_prioritization", static_script)
        self.assertIn("office-priority-grid", style_text)
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
        self.assertIn("Downloadable deliverables: 7", completed.stdout)
        self.assertIn("Reviewable catalog: 8 files", completed.stdout)
        self.assertIn("Visitor acceptance guide: 7 steps / downloads=8 / live=external_required", completed.stdout)
        self.assertIn("Handoff recovery inventory: 6 items / actions=regenerate_images", completed.stdout)
        self.assertIn("Fast review route: 5/5", completed.stdout)
        self.assertIn("Reading guide: 8/8", completed.stdout)
        self.assertIn("First-run paths: 3", completed.stdout)
        self.assertIn("Downstream quick-start: 5 steps", completed.stdout)
        self.assertIn("Shot contract: 4 fields", completed.stdout)
        self.assertIn("Reproducibility checklist: 5 commands", completed.stdout)
        self.assertIn("Real output validation: 3/3 steps", completed.stdout)
        self.assertIn("Release badge: safe_public_demo", completed.stdout)
        self.assertIn("Comic claim report: data/comic_production_claim_report.json / ready=True", completed.stdout)
        self.assertIn("Claim upgrade checklist: 4 items", completed.stdout)
        self.assertIn("Claim upgrade recovery: action=regenerate_images / steps=3", completed.stdout)
        self.assertIn("Real quality upgrade plan: status=blocked_until_real_model_evidence / steps=5 / models=3 / recovery=regenerate_images", completed.stdout)
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

    def test_live_showcase_verifier_checks_deployed_static_url(self):
        export_public_showcase(self.output_dir)
        handler = partial(SimpleHTTPRequestHandler, directory=str(self.output_dir))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            time.sleep(0.2)
            url = f"http://127.0.0.1:{server.server_port}/"
            payload = verify_public_showcase_live(url, timeout=15)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "public_no_key_live_showcase")
        self.assertEqual(payload["checked_files"], 8)
        self.assertEqual(payload["download_count"], 7)
        self.assertGreaterEqual(payload["visitor_step_count"], 5)
        self.assertEqual(payload["claim_level"], "demo_structure_only")
        self.assertEqual(payload["errors"], [])


if __name__ == "__main__":
    unittest.main()
