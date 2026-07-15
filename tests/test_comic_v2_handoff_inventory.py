import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_comic_v2_handoffs import audit_handoff_inventory, format_markdown
from scripts.verify_comic_v2_delivery import verify_delivery
from src.comic_office.v2.visual_review import REVIEW_DIMENSIONS


FIXTURE = Path("tests/fixtures/comic_v2_sample.json")


def _fixture_manifest(root: Path) -> dict:
    result = verify_delivery(FIXTURE, root)
    return json.loads(Path(result["handoff_manifest_path"]).read_text(encoding="utf-8"))


def _write_manifest(root: Path, name: str, payload: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class ComicV2HandoffInventoryTests(unittest.TestCase):
    def test_inventory_classifies_fixture_as_demo_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = _fixture_manifest(root)
            _write_manifest(root, "demo_handoff_manifest.json", manifest)

            inventory = audit_handoff_inventory([root])

        self.assertEqual(inventory["status"], "passed")
        self.assertEqual(inventory["manifest_count"], 2)
        self.assertGreaterEqual(inventory["demo_only_count"], 1)
        self.assertEqual(inventory["production_verified_count"], 0)
        self.assertIn("不能宣称真实画质", inventory["next_action"])
        self.assertTrue(all(item["word_canvas_exists"] for item in inventory["manifests"]))

    def test_inventory_rejects_real_provider_without_visual_review_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = _fixture_manifest(root)
            for image in manifest["images"]:
                image["provider"] = "doubao"
                image["model"] = "seedream"
                image["review"] = {"status": "pass", "handoff_ready": True, "scores": {}}
            _write_manifest(root, "real_missing_review_handoff_manifest.json", manifest)

            inventory = audit_handoff_inventory([root])

        target = next(item for item in inventory["manifests"] if item["visual_evidence_level"] == "model_reviewed")
        self.assertEqual(target["quality_claim"], "needs_review")
        self.assertEqual(target["recommended_recovery"]["action"], "regenerate_images")
        self.assertGreater(target["issue_count"], 0)

    def test_inventory_accepts_real_provider_with_seven_dimension_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = _fixture_manifest(root)
            for image in manifest["images"]:
                image["provider"] = "doubao"
                image["model"] = "seedream"
                image["review"] = {
                    "status": "pass",
                    "handoff_ready": True,
                    "fixture": False,
                    "scores": {dimension: 92 for dimension in REVIEW_DIMENSIONS},
                }
            _write_manifest(root, "real_verified_handoff_manifest.json", manifest)

            inventory = audit_handoff_inventory([root])

        target = next(item for item in inventory["manifests"] if item["production_quality_verified"])
        self.assertEqual(target["quality_claim"], "production_quality_verified")
        self.assertEqual(inventory["production_verified_count"], 1)
        self.assertIn("真实质量通过", inventory["next_action"])

    def test_inventory_skips_non_comic_manifests_and_marks_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "browser_extension_handoff_manifest.json").write_text(
                '{"manifest_version": 3, "name": "not comic"}',
                encoding="utf-8",
            )
            legacy = copy.deepcopy(_fixture_manifest(root))
            legacy["schema_version"] = 2
            legacy.pop("quality_benchmark", None)
            _write_manifest(root, "legacy_handoff_manifest.json", legacy)

            inventory = audit_handoff_inventory([root])
            markdown = format_markdown(inventory)

        self.assertEqual(inventory["manifest_count"], 2)
        self.assertIn("legacy_unverifiable", {item["quality_claim"] for item in inventory["manifests"]})
        self.assertNotIn("not comic", markdown)
        self.assertIn("AI Comic V2 Handoff Inventory", markdown)


if __name__ == "__main__":
    unittest.main()
