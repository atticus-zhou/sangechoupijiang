import json
import subprocess
import sys
import unittest

from fastapi.testclient import TestClient

from src.web.app import app


class ComicRealQualityUpgradePlanTests(unittest.TestCase):
    def test_upgrade_plan_endpoint_is_no_key_and_actionable(self):
        client = TestClient(app)
        response = client.get("/api/demo/comic-production/real-quality-upgrade-plan")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "no_key_real_quality_upgrade_plan")
        self.assertFalse(payload["requires_api_key"])
        self.assertFalse(payload["calls_real_models"])
        self.assertFalse(payload["writes_workspace"])
        self.assertEqual(payload["current_claim_level"], "demo_structure_only")
        self.assertEqual(payload["target_claim_level"], "real_quality_verified")
        self.assertEqual(payload["upgrade_status"], "blocked_until_real_model_evidence")
        self.assertFalse(payload["handoff_allowed_now"])
        self.assertFalse(payload["can_claim_real_quality_now"])
        self.assertEqual(
            {item["department_id"] for item in payload["model_preflight_departments"]},
            {"gongbu", "xingbu", "bingbu"},
        )
        self.assertEqual(
            [item["phase"] for item in payload["operator_steps"]],
            ["preflight", "recover_images", "visual_review", "rebuild_delivery", "release_claim"],
        )
        evidence = payload["evidence_contract"]
        self.assertFalse(evidence["ready_for_real_quality_claim"])
        self.assertIn("non_fixture_images", evidence["missing_check_ids"])
        self.assertIn("provider_model_bound", evidence["missing_check_ids"])
        self.assertGreaterEqual(evidence["seven_dimension_scored_reviews"], 7)
        self.assertEqual(payload["recovery_action"], "regenerate_images")
        self.assertIn("prompt_package", payload["preserves"])
        self.assertIn("visual_review", payload["rebuilds"])
        commands = "\n".join(payload["verification_commands"])
        self.assertIn("verify_comic_real_production_claim.py", commands)
        self.assertIn("verify_comic_v2_production_benchmark.py", commands)
        self.assertIn("verify_comic_v2_downstream_handoff.py", commands)
        self.assertIn("check_no_secrets.py", commands)
        self.assertIn("不读取 API Key", payload["public_boundary"])
        card = payload["human_upgrade_card"]
        self.assertIn("结构样例升级到真实制片质量", card["title"])
        self.assertIn("不要重写故事", card["summary"])
        self.assertIn("工部", " ".join(card["user_only_needs_to"]))
        transition = payload["artifact_transition_policy"]
        self.assertIn("同一份结构样例升级", transition["human_summary"])
        self.assertGreaterEqual(len(transition["preserve"]), 4)
        self.assertGreaterEqual(len(transition["invalidate"]), 3)
        self.assertGreaterEqual(len(transition["rebuild"]), 4)
        self.assertTrue(any(item["artifact"] == "已确认故事" for item in transition["preserve"]))
        self.assertTrue(any(item["artifact"] == "fixture 图片证据" for item in transition["invalidate"]))
        self.assertTrue(any(item["owner"] == "工部" for item in transition["rebuild"]))
        ladder = payload["acceptance_ladder"]
        self.assertEqual([item["level"] for item in ladder], ["demo_structure_only", "model_reviewed", "real_quality_verified"])
        ladder_text = json.dumps(ladder, ensure_ascii=False)
        self.assertIn("不能说真实画质", ladder_text)
        self.assertIn("provider/model/image_id", ladder_text)
        self.assertIn("handoff_allowed=true", ladder_text)
        self.assertNotIn("E:\\", json.dumps(payload, ensure_ascii=False))

    def test_verifier_json_and_markdown(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_real_quality_upgrade_plan.py",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["current_claim_level"], "demo_structure_only")
        self.assertEqual(payload["target_claim_level"], "real_quality_verified")
        self.assertEqual(payload["upgrade_status"], "blocked_until_real_model_evidence")
        self.assertEqual(payload["operator_step_count"], 5)
        self.assertEqual(payload["recovery_action"], "regenerate_images")
        self.assertEqual(payload["acceptance_ladder_count"], 3)
        self.assertEqual(payload["artifact_transition_preserve_count"], 4)

        markdown = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_real_quality_upgrade_plan.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertIn("AI Comic Real Quality Upgrade Plan", markdown.stdout)
        self.assertIn("Target claim: `real_quality_verified`", markdown.stdout)
        self.assertIn("Recovery action: `regenerate_images`", markdown.stdout)
        self.assertIn("Human Upgrade Card", markdown.stdout)
        self.assertIn("Artifact Transition Policy", markdown.stdout)
        self.assertIn("Acceptance Ladder", markdown.stdout)


if __name__ == "__main__":
    unittest.main()
