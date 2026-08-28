import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_comic_v2_delivery import verify_delivery
from src.comic_office.v2.production_benchmark import audit_handoff_manifest


FIXTURE = Path("tests/fixtures/comic_v2_sample.json")


def fixture_manifest(root: Path) -> dict:
    result = verify_delivery(FIXTURE, root)
    return json.loads(Path(result["handoff_manifest_path"]).read_text(encoding="utf-8"))


class ComicV2ProductionBenchmarkTests(unittest.TestCase):
    def test_fixture_is_honest_structure_demo_not_real_quality_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = audit_handoff_manifest(fixture_manifest(Path(tmp)))

        self.assertEqual(audit["status"], "demo_structure_verified")
        self.assertEqual(audit["package_quality_score"], 100)
        self.assertTrue(audit["package_quality_ready"])
        self.assertFalse(audit["production_quality_verified"])
        self.assertEqual(audit["visual_evidence_level"], "fixture_only")
        self.assertEqual(audit["image_quality_summary"]["total_images"], 7)
        self.assertEqual(audit["image_quality_summary"]["usable_images"], 7)
        self.assertEqual(audit["image_quality_summary"]["waste_or_rework_images"], 0)
        self.assertEqual(audit["image_quality_summary"]["waste_or_rework_rate"], 0)
        by_asset_type = audit["image_quality_summary"]["by_asset_type"]
        self.assertEqual(by_asset_type["character"]["total"], 2)
        self.assertEqual(by_asset_type["character"]["passed"], 2)
        self.assertEqual(by_asset_type["prop"]["total"], 2)
        self.assertEqual(by_asset_type["prop"]["passed"], 2)
        self.assertEqual(by_asset_type["scene"]["total"], 3)
        self.assertEqual(by_asset_type["scene"]["passed"], 3)
        self.assertEqual(by_asset_type["scene"]["waste_or_rework_rate"], 0)
        self.assertEqual(audit["prompt_quality_summary"]["status"], "ready")
        self.assertEqual(audit["prompt_quality_summary"]["asset_prompt_count"], 7)
        self.assertEqual(audit["prompt_quality_summary"]["clean_asset_prompt_count"], 7)
        self.assertEqual(audit["prompt_quality_summary"]["shot_prompt_count"], 2)
        self.assertEqual(audit["prompt_quality_summary"]["director_prompt_count"], 2)
        self.assertEqual(audit["prompt_quality_summary"]["issue_count"], 0)
        real_model_evidence = audit["real_model_evidence_requirements"]
        self.assertEqual(real_model_evidence["seven_dimension_scored_reviews"], 7)
        self.assertNotIn("seven_dimension_scores", real_model_evidence["missing_check_ids"])
        self.assertIn("non_fixture_images", real_model_evidence["missing_check_ids"])
        self.assertIn("provider_model_bound", real_model_evidence["missing_check_ids"])
        self.assertIn("不证明真实模型", audit["limitations"][0])
        self.assertEqual(audit["recommended_recovery"], {})

    def test_story_tampering_blocks_handoff_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        manifest["story"]["source_story"] = "故事被替换。"

        audit = audit_handoff_manifest(manifest)

        issue_codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["status"], "needs_review")
        self.assertFalse(audit["package_quality_ready"])
        self.assertIn("story.source_hash", issue_codes)
        self.assertIn("story.asset_evidence", issue_codes)
        self.assertIn("story.shot_evidence", issue_codes)
        self.assertEqual(audit["recommended_recovery"]["action"], "restart_story_review")
        self.assertIn("内阁", audit["recommended_recovery"]["department"])

    def test_story_evidence_issues_return_to_the_earliest_responsible_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            asset_manifest = fixture_manifest(Path(tmp))
        asset_manifest["assets"][0]["evidence_quote"] = "故事里不存在的资产依据"

        asset_audit = audit_handoff_manifest(asset_manifest)

        self.assertEqual(asset_audit["recommended_recovery"]["reason_code"], "story.asset_evidence")
        self.assertEqual(asset_audit["recommended_recovery"]["action"], "revise_assets")

        with tempfile.TemporaryDirectory() as tmp:
            shot_manifest = fixture_manifest(Path(tmp))
        shot_manifest["shots"][0]["evidence_quote"] = "故事里不存在的镜头依据"

        shot_audit = audit_handoff_manifest(shot_manifest)

        self.assertEqual(shot_audit["recommended_recovery"]["reason_code"], "story.shot_evidence")
        self.assertEqual(shot_audit["recommended_recovery"]["action"], "regenerate_prompts")

    def test_missing_planned_image_returns_to_image_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        asset = manifest["assets"][0]
        baseline_id = asset["identity_baseline_image_id"]
        removable = next(
            image
            for image in manifest["images"]
            if image.get("asset_id") == asset["asset_id"]
            and image.get("image_id") != baseline_id
        )
        manifest["images"].remove(removable)

        audit = audit_handoff_manifest(manifest)

        self.assertEqual(audit["recommended_recovery"]["reason_code"], "asset.image_coverage")
        self.assertEqual(audit["recommended_recovery"]["action"], "regenerate_images")

    def test_cross_asset_template_copy_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        original_asset = manifest["assets"][0]
        duplicate_asset = copy.deepcopy(original_asset)
        duplicate_asset["asset_id"] = "character_template_copy"
        duplicate_asset["name"] = "模板复制角色"
        duplicate_asset["image_ids"] = []
        duplicate_asset["image_ids_by_kind"] = {}
        duplicate_asset["identity_baseline_image_id"] = ""
        original_images = [
            item for item in manifest["images"]
            if item["asset_id"] == original_asset["asset_id"]
        ]
        for image in original_images:
            clone = copy.deepcopy(image)
            clone["asset_id"] = duplicate_asset["asset_id"]
            clone["image_id"] = image["image_id"].replace(original_asset["asset_id"], duplicate_asset["asset_id"])
            clone["generator_prompt"] = clone["generator_prompt"].replace(
                original_asset["asset_id"], duplicate_asset["asset_id"]
            ).replace(original_asset["name"], duplicate_asset["name"])
            duplicate_asset["image_ids"].append(clone["image_id"])
            duplicate_asset["image_ids_by_kind"][clone["image_kind"]] = clone["image_id"]
            if clone["is_identity_baseline"]:
                duplicate_asset["identity_baseline_image_id"] = clone["image_id"]
                duplicate_asset["identity_baseline_image_kind"] = clone["image_kind"]
            manifest["images"].append(clone)
        manifest["assets"].append(duplicate_asset)

        audit = audit_handoff_manifest(manifest)

        issue_codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["status"], "needs_review")
        self.assertIn("prompt.cross_asset_uniqueness", issue_codes)
        self.assertEqual(audit["prompt_quality_summary"]["status"], "needs_review")
        self.assertEqual(audit["prompt_quality_summary"]["issue_count"], 2)
        self.assertEqual(audit["prompt_quality_summary"]["clean_asset_prompt_count"], 7)
        self.assertEqual(audit["recommended_recovery"]["action"], "regenerate_prompts")

    def test_prompt_package_issues_are_exposed_as_first_class_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        manifest["images"][0]["negative_prompt"] = []

        audit = audit_handoff_manifest(manifest)

        summary = audit["prompt_quality_summary"]
        issue_codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(summary["status"], "needs_review")
        self.assertEqual(summary["issue_count"], 2)
        self.assertEqual(summary["asset_prompt_count"], 7)
        self.assertEqual(summary["clean_asset_prompt_count"], 6)
        self.assertLessEqual(len(summary["issues"]), 10)
        self.assertIn("prompt.executable_structure", issue_codes)
        self.assertEqual(audit["recommended_recovery"]["action"], "regenerate_prompts")

    def test_asset_prompts_must_inherit_visual_bible_style_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        lighting = manifest["style"]["lighting"]
        self.assertIn(lighting, manifest["images"][0]["generator_prompt"])
        manifest["images"][0]["generator_prompt"] = manifest["images"][0]["generator_prompt"].replace(lighting, "")

        audit = audit_handoff_manifest(manifest)

        issue_codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["status"], "needs_review")
        self.assertIn("prompt.visual_bible_transfer", issue_codes)
        self.assertEqual(audit["recommended_recovery"]["action"], "regenerate_prompts")

    def test_shot_prompt_requires_first_frame_and_reference_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        manifest["shots"][0]["first_frame_reference_image"] = {}
        manifest["shots"][0]["reference_asset_chain"] = []

        audit = audit_handoff_manifest(manifest)

        summary = audit["prompt_quality_summary"]
        issue_codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(summary["status"], "needs_review")
        self.assertGreater(summary["issue_count"], 0)
        self.assertIn("prompt.executable_structure", issue_codes)
        self.assertEqual(audit["recommended_recovery"]["action"], "regenerate_prompts")

    def test_real_provider_requires_seven_dimension_visual_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        for image in manifest["images"]:
            image["provider"] = "doubao"
            image["model"] = "seedream"
            image["review"] = {
                "status": "pass",
                "handoff_ready": True,
                "scores": {},
            }

        audit = audit_handoff_manifest(manifest)

        issue_codes = {item["code"] for item in audit["issues"]}
        self.assertEqual(audit["visual_evidence_level"], "model_reviewed")
        self.assertFalse(audit["production_quality_verified"])
        self.assertIn("visual.review_dimensions", issue_codes)
        self.assertEqual(audit["image_quality_summary"]["total_images"], 7)
        self.assertEqual(audit["image_quality_summary"]["usable_images"], 0)
        self.assertEqual(audit["image_quality_summary"]["waste_or_rework_images"], 7)
        self.assertEqual(audit["image_quality_summary"]["waste_or_rework_rate"], 1)
        by_asset_type = audit["image_quality_summary"]["by_asset_type"]
        self.assertEqual(by_asset_type["character"]["waste_or_rework"], 2)
        self.assertEqual(by_asset_type["prop"]["waste_or_rework"], 2)
        self.assertEqual(by_asset_type["scene"]["waste_or_rework"], 3)
        self.assertEqual(by_asset_type["character"]["waste_or_rework_rate"], 1)
        self.assertIn("img_", audit["image_quality_summary"]["failed_image_ids"][0])
        instructions = audit["image_quality_summary"]["rework_instructions"]
        self.assertEqual(len(instructions), 7)
        self.assertEqual(instructions[0]["action"], "manual_review")
        self.assertTrue(instructions[0]["label"])
        self.assertTrue(all(item["reason"].strip() for item in instructions))
        self.assertIn("\u4e03\u7ef4\u8bc4\u5206", instructions[0]["reason"])
        self.assertIn("operator_steps", instructions[0])
        self.assertEqual(instructions[0]["priority"], "medium")
        self.assertEqual(instructions[0]["blocked_stage"], "人工复核")
        self.assertTrue(instructions[0]["blocks_downstream"])
        self.assertIn("人工判断", instructions[0]["user_message"])
        self.assertEqual(instructions[0]["next_button_label"], "人工复核")
        self.assertEqual(audit["recommended_recovery"]["action"], "regenerate_images")

    def test_missing_visual_review_creates_rerun_review_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        manifest["images"][0]["review"] = {}

        audit = audit_handoff_manifest(manifest)

        first = audit["image_quality_summary"]["rework_instructions"][0]
        by_asset_type = audit["image_quality_summary"]["by_asset_type"]
        self.assertEqual(by_asset_type["character"]["waste_or_rework"], 1)
        self.assertIn(manifest["images"][0]["image_id"], by_asset_type["character"]["failed_image_ids"])
        self.assertEqual(first["action"], "rerun_visual_review")
        self.assertEqual(first["label"], "补跑视觉质检")
        self.assertEqual(first["department"], "刑部")
        self.assertEqual(first["blocked_stage"], "视觉质检")
        self.assertEqual(first["next_button_label"], "重跑视觉质检")
        self.assertIn("七维评分", "；".join(first["operator_steps"]))
        summary = audit["image_quality_summary"]["rework_action_summary"][0]
        self.assertEqual(summary["action"], "rerun_visual_review")
        self.assertEqual(summary["count"], 1)

    def test_recommended_recovery_includes_operator_playbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fixture_manifest(Path(tmp))
        asset = manifest["assets"][0]
        baseline_id = asset["identity_baseline_image_id"]
        removable = next(
            image
            for image in manifest["images"]
            if image.get("asset_id") == asset["asset_id"]
            and image.get("image_id") != baseline_id
        )
        manifest["images"].remove(removable)

        audit = audit_handoff_manifest(manifest)
        recovery = audit["recommended_recovery"]

        self.assertEqual(recovery["action"], "regenerate_images")
        self.assertEqual(recovery["expected_stage"], "image_generation")
        self.assertIn("prompt_package", recovery["preserves"])
        self.assertIn("image_production", recovery["clears"])
        self.assertGreaterEqual(len(recovery["operator_steps"]), 2)
        self.assertTrue(all(step.strip() for step in recovery["operator_steps"]))


if __name__ == "__main__":
    unittest.main()
