import unittest

from src.comic_office.v2.asset_manifest import (
    ManifestValidationError,
    NoManifestChangeError,
    build_asset_manifest,
    asset_manifest_from_dict,
    replace_asset_manifest,
    revise_asset_manifest,
)
from src.comic_office.v2.contracts import build_contract_bundle


STORY = (
    "林昭在月税司登记月灯，发现裂纹月灯里出现亡兄林晦的影子。"
    "她带着裂纹月灯找到修灯匠顾砚，并在修灯铺查到月税簿。"
    "两人前往中央月塔，林昭最终熄灭月塔，让全城重新想起被遗忘的亲人。"
)


def contract_bundle():
    return build_contract_bundle(
        STORY,
        {
            "title": "借月人",
            "genre": "古风幻想",
            "theme": "记忆与光明的代价",
            "protagonist_goal": "找回被抹去的哥哥",
            "main_conflict": "月塔燃烧记忆维持城市光明",
            "causal_chain": ["发现亡兄影子", "查到月税真相", "熄灭月塔"],
            "ending": "林昭熄灭月塔",
            "episodes": [{"episode": 1, "summary": "追查月灯", "evidence_quote": "林昭在月税司登记月灯"}],
            "visual": {
                "medium": "电影级国风厚涂动画",
                "era": "架空古代",
                "aspect_ratio": "9:16",
                "palette": ["靛青", "银白", "暗朱红"],
                "lighting": "冷月光与暖灯火对照",
                "camera_language": "克制稳定",
                "character_rules": ["脸型固定"],
                "costume_rules": ["古代服装"],
                "prop_rules": ["裂纹位置固定"],
                "architecture_rules": ["木石结构"],
                "visual_motifs": ["裂纹月灯"],
                "prohibited_elements": ["现代车辆"],
            },
        },
    )


VALID_ASSETS = [
    {
        "asset_type": "character",
        "name": "林昭",
        "evidence_quote": "林昭在月税司登记月灯",
        "scene_ids": ["scene_01", "scene_03"],
        "story_purpose": "主角，发现并终结月税真相",
        "visual_locks": ["靛青窄袖长袍", "固定发髻"],
        "allowed_changes": ["表情", "姿势"],
    },
    {
        "asset_type": "scene",
        "name": "月税司",
        "evidence_quote": "月税司",
        "scene_ids": ["scene_01"],
        "story_purpose": "制度日常与异常发生地",
        "visual_locks": ["中央长柜", "悬吊月灯"],
        "allowed_changes": ["群众数量"],
    },
]


class ComicV2AssetManifestTests(unittest.TestCase):
    def test_asset_without_source_evidence_is_rejected(self):
        invalid = [{
            "asset_type": "prop",
            "name": "不存在的剑",
            "evidence_quote": "故事从未出现过这把剑",
            "scene_ids": ["scene_01"],
            "story_purpose": "装饰",
            "visual_locks": ["青铜剑身"],
            "allowed_changes": ["角度"],
        }]

        with self.assertRaises(ManifestValidationError):
            build_asset_manifest(contract_bundle(), invalid)

    def test_asset_types_receive_production_default_images(self):
        assets = VALID_ASSETS + [{
            "asset_type": "prop",
            "name": "裂纹月灯",
            "evidence_quote": "裂纹月灯",
            "scene_ids": ["scene_01", "scene_02", "scene_03"],
            "story_purpose": "贯穿真相与结局的核心道具",
            "visual_locks": ["裂纹位置固定"],
            "allowed_changes": ["发光强度"],
        }]

        manifest = build_asset_manifest(contract_bundle(), assets)
        by_name = {item.name: item for item in manifest.items}

        self.assertEqual(by_name["林昭"].planned_images, ("three_view", "expression_sheet"))
        self.assertEqual(by_name["裂纹月灯"].planned_images, ("turnaround", "state_sheet"))
        self.assertEqual(by_name["月税司"].planned_images, ("wide", "top_down", "camera_angles"))

    def test_revision_applies_user_request_and_changes_hash(self):
        first = build_asset_manifest(contract_bundle(), VALID_ASSETS)
        moon_lamp = {
            "asset_type": "prop",
            "name": "裂纹月灯",
            "evidence_quote": "裂纹月灯",
            "scene_ids": ["scene_01", "scene_02", "scene_03"],
            "story_purpose": "贯穿真相与结局的核心道具",
            "visual_locks": ["裂纹位置固定"],
            "allowed_changes": ["发光强度"],
        }

        second = revise_asset_manifest(first, "缺少贯穿故事的裂纹月灯", [moon_lamp])

        self.assertNotEqual(first.manifest_hash, second.manifest_hash)
        self.assertEqual(second.version, first.version + 1)
        self.assertEqual(second.revision_note, "缺少贯穿故事的裂纹月灯")
        self.assertIn("裂纹月灯", [item.name for item in second.items])
        self.assertIn("林昭", [item.name for item in second.items])
        self.assertEqual(first.review_status, "awaiting_user_review")
        self.assertEqual(second.review_status, "awaiting_user_review")

    def test_noop_revision_is_rejected(self):
        first = build_asset_manifest(contract_bundle(), VALID_ASSETS)

        with self.assertRaises(NoManifestChangeError):
            revise_asset_manifest(first, "重新拆解", VALID_ASSETS)

    def test_asset_ids_stay_stable_when_new_item_is_added(self):
        first = build_asset_manifest(contract_bundle(), VALID_ASSETS)
        added = revise_asset_manifest(first, "补充顾砚", [{
            "asset_type": "character",
            "name": "顾砚",
            "evidence_quote": "修灯匠顾砚",
            "scene_ids": ["scene_02", "scene_03"],
            "story_purpose": "解释真相并协助主角",
            "visual_locks": ["黑纱蒙眼"],
            "allowed_changes": ["表情", "姿势"],
        }])

        first_ids = {item.name: item.asset_id for item in first.items}
        second_ids = {item.name: item.asset_id for item in added.items}
        self.assertEqual(first_ids["林昭"], second_ids["林昭"])
        self.assertEqual(first_ids["月税司"], second_ids["月税司"])

    def test_manifest_round_trip_restores_source_story_for_later_revision(self):
        first = build_asset_manifest(contract_bundle(), VALID_ASSETS)

        restored = asset_manifest_from_dict(first.to_dict(), source_story=STORY)

        self.assertEqual(restored, first)
        self.assertEqual(restored.source_story, STORY)

    def test_full_replacement_can_remove_an_incorrect_asset(self):
        first = build_asset_manifest(contract_bundle(), VALID_ASSETS)
        corrected = [VALID_ASSETS[0], {
            "asset_type": "prop",
            "name": "裂纹月灯",
            "evidence_quote": "裂纹月灯",
            "scene_ids": ["scene_01", "scene_02"],
            "story_purpose": "推动真相被发现的核心证物",
            "visual_locks": ["裂纹位置固定"],
            "allowed_changes": ["发光强度"],
        }]

        second = replace_asset_manifest(first, "删除错误场景并补充核心道具", corrected)

        self.assertEqual(second.version, 2)
        self.assertEqual({item.name for item in second.items}, {"林昭", "裂纹月灯"})
        self.assertNotEqual(second.manifest_hash, first.manifest_hash)


if __name__ == "__main__":
    unittest.main()
