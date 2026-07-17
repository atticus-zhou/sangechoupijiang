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
        self.assertNotIn("E:\\", json.dumps(claim_payload, ensure_ascii=False))
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
        self.assertEqual(deploy_manifest["mode"], "public_no_key_portfolio_deploy")
        self.assertEqual(deploy_manifest["source_dir"], "dist/public-showcase")
        self.assertEqual(deploy_manifest["personal_site_target"], "public/three-stooges/")
        self.assertEqual(deploy_manifest["personal_site_url_path"], "/three-stooges/")
        self.assertFalse(deploy_manifest["requires_backend"])
        self.assertFalse(deploy_manifest["requires_api_key"])
        self.assertFalse(deploy_manifest["calls_real_models"])
        self.assertFalse(deploy_manifest["allows_workspace_writes"])
        self.assertEqual(deploy_manifest["sample_download_count"], 6)
        self.assertIn("downloads/", deploy_manifest["required_files"])
        self.assertIn("config.yaml", " ".join(deploy_manifest["forbidden_public_assets"]))
        self.assertTrue(any("verify_static_public_showcase.py" in item for item in deploy_manifest["verification_commands"]))
        self.assertGreaterEqual(len(deploy_manifest["operator_checklist"]), 4)
        quick_start = showcase["portfolio_embed"]["downstream_quick_start"]
        self.assertEqual([item["step"] for item in quick_start], [1, 2, 3, 4, 5])
        self.assertIn("逐镜头生成视频", json.dumps(quick_start, ensure_ascii=False))
        self.assertTrue(all(item["owner"] and item["acceptance"] for item in quick_start))
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
        self.assertIn("renderReleaseBadge", static_script)
        self.assertIn("renderDownstreamQuickStart", static_script)
        self.assertIn("renderReproducibilityChecklist", static_script)
        self.assertIn("真实产物验收", index_text)
        self.assertIn("renderPostRunValidation", static_script)
        self.assertIn("portfolio.post_run_validation", static_script)
        self.assertIn("prompt_quality_summary", static_script)
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
        self.assertIn("Downstream quick-start: 5 steps", completed.stdout)
        self.assertIn("Reproducibility checklist: 5 commands", completed.stdout)
        self.assertIn("Real output validation: 3/3 steps", completed.stdout)
        self.assertIn("Release badge: safe_public_demo", completed.stdout)
        self.assertIn("Comic claim report: data/comic_production_claim_report.json / ready=True", completed.stdout)
        self.assertIn("Claim upgrade checklist: 3 items", completed.stdout)
        self.assertIn("Quality upgrade path: action=regenerate_images / steps=3", completed.stdout)
        self.assertIn("Prompt quality: ready / assets=7/7 / directors=2/2 / issues=0", completed.stdout)
        self.assertIn("Portfolio integration: source=dist/public-showcase / options=2", completed.stdout)
        self.assertIn("Portfolio deploy manifest: portfolio-deploy-manifest.json / target=public/three-stooges/", completed.stdout)
        self.assertIn("Requires backend: False", completed.stdout)


if __name__ == "__main__":
    unittest.main()
