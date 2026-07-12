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
        self.assertIn("不证明真实模型", audit["limitations"][0])

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


if __name__ == "__main__":
    unittest.main()
