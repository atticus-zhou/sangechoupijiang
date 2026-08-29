import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_public_demo_mode.py")


class PublicDemoVerifierTests(unittest.TestCase):
    def test_json_verifies_no_key_demo_endpoints_and_downloads(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "public_no_key_demo")
        self.assertEqual(payload["showcase_manifest"]["status_code"], 200)
        self.assertEqual(payload["showcase_manifest"]["mode"], "public_no_key_showcase")
        self.assertGreaterEqual(payload["showcase_manifest"]["audience_path_count"], 3)
        self.assertGreaterEqual(payload["showcase_manifest"]["featured_demo_count"], 2)
        self.assertEqual(payload["showcase_manifest"]["fast_review_count"], 5)
        self.assertEqual(
            payload["showcase_manifest"]["fast_review_count"],
            payload["showcase_manifest"]["fast_review_ready_count"],
        )
        self.assertGreaterEqual(payload["showcase_manifest"]["reading_guide_count"], 4)
        self.assertEqual(
            payload["showcase_manifest"]["reading_guide_count"],
            payload["showcase_manifest"]["reading_guide_ready_count"],
        )
        self.assertGreaterEqual(payload["showcase_manifest"]["interview_script_count"], 4)
        self.assertEqual(
            payload["showcase_manifest"]["interview_script_count"],
            payload["showcase_manifest"]["interview_script_ready_count"],
        )
        self.assertGreaterEqual(payload["showcase_manifest"]["reproducibility_count"], 5)
        self.assertEqual(
            payload["showcase_manifest"]["reproducibility_count"],
            payload["showcase_manifest"]["reproducibility_ready_count"],
        )
        self.assertEqual(payload["showcase_manifest"]["release_badge_status"], "safe_public_demo")
        self.assertGreaterEqual(payload["showcase_manifest"]["release_badge_signal_count"], 5)
        self.assertFalse(payload["showcase_manifest"]["release_badge_claim_real_quality"])
        self.assertEqual(payload["showcase_manifest"]["office_extension_checklist_count"], 8)
        self.assertEqual(payload["showcase_manifest"]["office_extension_phase_count"], 8)
        self.assertEqual(
            payload["showcase_manifest"]["office_extension_doc"],
            "docs/NEW_OFFICE_STARTER_CHECKLIST.md",
        )
        self.assertEqual(payload["showcase_manifest"]["office_extension_candidate_count"], 4)
        self.assertEqual(payload["showcase_manifest"]["office_extension_backlog_count"], 2)
        self.assertEqual(payload["showcase_manifest"]["office_launch_office_count"], 3)
        self.assertEqual(payload["showcase_manifest"]["office_launch_public_ready_count"], 2)
        self.assertEqual(payload["showcase_manifest"]["office_launch_primary_allowed_count"], 1)
        self.assertEqual(payload["showcase_manifest"]["office_launch_legacy_count"], 1)
        self.assertEqual(
            payload["showcase_manifest"]["handoff_inventory_uri"],
            "/api/demo/comic-production/handoff-inventory",
        )
        self.assertEqual(payload["showcase_manifest"]["handoff_inventory_production_verified_count"], 0)
        self.assertGreaterEqual(payload["showcase_manifest"]["handoff_inventory_image_quality_item_count"], 1)
        self.assertGreaterEqual(payload["showcase_manifest"]["handoff_inventory_total_images"], 7)
        self.assertGreaterEqual(payload["showcase_manifest"]["handoff_inventory_usable_images"], 7)
        self.assertGreaterEqual(payload["showcase_manifest"]["handoff_inventory_waste_or_rework_images"], 0)
        self.assertGreaterEqual(payload["showcase_manifest"]["handoff_inventory_waste_or_rework_rate"], 0)
        showcase_asset_types = payload["showcase_manifest"]["handoff_inventory_asset_type_quality"]
        self.assertGreaterEqual(showcase_asset_types["character"]["total"], 2)
        self.assertGreaterEqual(showcase_asset_types["prop"]["total"], 2)
        self.assertGreaterEqual(showcase_asset_types["scene"]["total"], 3)
        self.assertEqual(payload["showcase_manifest"]["asset_usage_map_ready_assets"], payload["showcase_manifest"]["asset_usage_map_total_assets"])
        self.assertGreaterEqual(payload["showcase_manifest"]["asset_usage_map_image_roles"], payload["showcase_manifest"]["asset_usage_map_total_assets"])
        self.assertEqual(payload["showcase_manifest"]["asset_usage_map_referenced_assets"], payload["showcase_manifest"]["asset_usage_map_total_assets"])
        self.assertIn("真实模型质量", payload["showcase_manifest"]["handoff_inventory_safe_public_claim"])
        self.assertEqual(
            payload["showcase_manifest"]["real_production_claim_uri"],
            "/api/demo/comic-production/claim-report",
        )
        self.assertEqual(payload["showcase_manifest"]["real_production_claim_level"], "demo_structure_only")
        self.assertFalse(payload["showcase_manifest"]["real_production_can_claim_real_quality"])
        self.assertEqual(payload["showcase_manifest"]["real_quality_upgrade_status"], "blocked_until_real_model_evidence")
        self.assertEqual(payload["showcase_manifest"]["real_quality_upgrade_step_count"], 5)
        self.assertEqual(payload["showcase_manifest"]["real_quality_upgrade_department_count"], 3)
        self.assertEqual(payload["showcase_manifest"]["real_quality_upgrade_recovery_action"], "regenerate_images")
        self.assertEqual(
            payload["showcase_manifest"]["static_export_command"],
            "python scripts/export_public_showcase.py",
        )
        self.assertEqual(payload["comic_handoff_inventory"]["status_code"], 200)
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["manifest_count"], 1)
        self.assertEqual(payload["comic_handoff_inventory"]["production_verified_count"], 0)
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["demo_only_count"], 1)
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["recovery_item_count"], 1)
        self.assertIn("regenerate_images", payload["comic_handoff_inventory"]["recovery_actions"])
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["recovery_stage_count"], 1)
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["image_quality_item_count"], 1)
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["total_images"], 7)
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["usable_images"], 7)
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["waste_or_rework_images"], 0)
        self.assertGreaterEqual(payload["comic_handoff_inventory"]["waste_or_rework_rate"], 0)
        inventory_asset_types = payload["comic_handoff_inventory"]["asset_type_quality"]
        self.assertGreaterEqual(inventory_asset_types["character"]["total"], 2)
        self.assertGreaterEqual(inventory_asset_types["prop"]["total"], 2)
        self.assertGreaterEqual(inventory_asset_types["scene"]["total"], 3)
        self.assertEqual(payload["comic_real_production_claim"]["status_code"], 200)
        self.assertEqual(payload["comic_real_production_claim"]["claim_level"], "demo_structure_only")
        self.assertFalse(payload["comic_real_production_claim"]["can_claim_real_quality"])
        self.assertEqual(payload["comic_real_production_claim"]["downstream_status"], "structure_demo_only")
        self.assertGreaterEqual(payload["comic_real_production_claim"]["upgrade_checklist_count"], 3)
        self.assertEqual(payload["comic_real_production_claim"]["recovery_action"], "regenerate_images")
        self.assertGreaterEqual(payload["comic_real_production_claim"]["recovery_step_count"], 3)
        self.assertTrue(payload["showcase_manifest"]["static_export_backend_free"])
        self.assertIn("comic_production", payload["demos"])
        self.assertIn("research", payload["demos"])
        comic_benchmark = payload["demos"]["comic_production"]["quality_benchmark"]
        self.assertEqual(comic_benchmark["status"], "demo_structure_verified")
        self.assertEqual(comic_benchmark["package_quality_score"], 100)
        self.assertFalse(comic_benchmark["production_quality_verified"])
        self.assertEqual(comic_benchmark["prompt_quality_summary"]["status"], "ready")
        self.assertEqual(comic_benchmark["prompt_quality_summary"]["issue_count"], 0)
        image_quality = comic_benchmark["image_quality_summary"]
        self.assertGreaterEqual(image_quality["total_images"], 7)
        self.assertGreaterEqual(image_quality["usable_images"], 0)
        self.assertGreaterEqual(image_quality["waste_or_rework_images"], 0)
        if image_quality["waste_or_rework_images"]:
            self.assertTrue(image_quality["rework_action_summary"])
            self.assertIsInstance(image_quality["rework_action_summary"][0], dict)
            self.assertEqual(image_quality["rework_action_summary"][0]["action"], "manual_review")
        self.assertNotIn("{'action'", json.dumps(image_quality["rework_action_summary"], ensure_ascii=False))
        self.assertEqual(
            payload["demos"]["comic_production"]["honest_quality_gate"]["status"],
            "passed",
        )
        for demo in payload["demos"].values():
            self.assertTrue(demo["available"] )
            self.assertFalse(demo["requires_api_key"] )
            self.assertFalse(demo["calls_real_models"] )
            self.assertTrue(demo["read_only"] )
            self.assertGreaterEqual(len(demo["downloads"]), 2)
            for item in demo["downloads"]:
                self.assertEqual(item["status_code"], 200)
                self.assertGreater(item["bytes"], 20)
                self.assertTrue(item["uri"].startswith("/api/demo/"))

        links = "\n".join(payload["launch_gate_links"])
        self.assertIn("/api/demo/comic-production/files/word_canvas.docx", links)
        self.assertIn("/api/demo/comic-production/files/handoff_manifest.json", links)
        self.assertIn("/api/demo/research/files/report.md", links)
        self.assertIn("/api/demo/research/files/evidence_manifest.json", links)
        self.assertNotIn("sk-", result.stdout.lower())

    def test_markdown_is_readable_for_public_showcase(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("公开演示模式验证", result.stdout)
        self.assertIn("AI 漫剧制片办公室", result.stdout)
        self.assertIn("研究办公室", result.stdout)
        self.assertIn("下载链接", result.stdout)
        self.assertIn("公开展示清单", result.stdout)
        self.assertIn("最快验收路线", result.stdout)
        self.assertIn("5 步，其中 5 步可复核", result.stdout)
        self.assertIn("交付物阅读顺序", result.stdout)
        self.assertIn("资产使用地图", result.stdout)
        self.assertIn("个图片角色", result.stdout)
        self.assertIn("面试演示脚本", result.stdout)
        self.assertIn("复现与验收清单", result.stdout)
        self.assertIn("发布状态铭牌", result.stdout)
        self.assertIn("safe_public_demo", result.stdout)
        self.assertIn("漫剧交付盘点", result.stdout)
        self.assertIn("漫剧交付恢复动作", result.stdout)
        self.assertIn("份可恢复", result.stdout)
        self.assertIn("不调用真实模型", result.stdout)
        self.assertIn("claim report", result.stdout)
        self.assertIn("upgrade_checklist=", result.stdout)
        self.assertIn("recovery=regenerate_images", result.stdout)
        self.assertIn("真实质量升级操作面板", result.stdout)
        self.assertIn("status=blocked_until_real_model_evidence", result.stdout)
        self.assertIn("steps=5", result.stdout)
        self.assertIn("action=regenerate_images", result.stdout)
        self.assertIn("source=dist/public-showcase", result.stdout)
        self.assertIn("New office extension: checklist=8 / phases=8 / doc=docs/NEW_OFFICE_STARTER_CHECKLIST.md", result.stdout)
        self.assertIn("Future office candidates: 4 / backlog=2", result.stdout)
        self.assertIn("Office launch matrix: public_ready=2/3 / primary=1 / legacy=1", result.stdout)
        self.assertIn("demo_structure_only", result.stdout)
        self.assertIn("demo_structure_verified", result.stdout)
        self.assertIn("Prompt quality: ready / assets=7/7 / directors=2/2 / issues=0", result.stdout)
        self.assertIn("已验证真实模型画质：False", result.stdout)


if __name__ == "__main__":
    unittest.main()

