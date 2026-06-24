import unittest

from src.comic_office.v2.contracts import (
    ContractValidationError,
    build_contract_bundle,
    contract_bundle_from_dict,
    story_hash,
)


class ComicV2ContractTests(unittest.TestCase):
    def test_contract_preserves_source_story_verbatim(self):
        story = "第一行。\n第二行，包含原始标点。"

        bundle = build_contract_bundle(
            story,
            {
                "title": "测试故事",
                "genre": "古风幻想",
                "theme": "记忆是否值得牺牲",
                "protagonist_goal": "找回被抹去的亲人",
                "main_conflict": "城市依赖被燃烧的记忆维持光明",
                "causal_chain": ["发现异常", "追查真相", "作出选择"],
                "ending": "主角熄灭月塔，城市迎来真正黎明",
                "episodes": [{"episode": 1, "summary": "发现异常", "evidence_quote": "第一行。"}],
                "visual": {
                    "medium": "电影级国风厚涂动画",
                    "era": "架空古代",
                    "aspect_ratio": "9:16",
                    "palette": ["靛青", "银白", "暗朱红"],
                    "lighting": "冷月光与暖灯火形成叙事对照",
                    "camera_language": "克制稳定，以缓慢移动表现压迫",
                    "character_rules": ["脸型与服装主色固定"],
                    "costume_rules": ["古代窄袖长袍"],
                    "prop_rules": ["材质和磨损位置固定"],
                    "architecture_rules": ["古代木石结构"],
                    "visual_motifs": ["裂纹月灯"],
                    "prohibited_elements": ["现代服装", "现代车辆"],
                },
            },
        )

        self.assertEqual(bundle.creative.source_story, story)
        self.assertEqual(bundle.creative.source_hash, story_hash(story))

    def test_ids_are_stable_across_retries(self):
        story = "同一个完整故事。"
        planner = self._planner()

        first = build_contract_bundle(story, planner)
        second = build_contract_bundle(story, planner)

        self.assertEqual(first.creative.story_id, second.creative.story_id)
        self.assertEqual(first.visual.style_id, second.visual.style_id)
        self.assertEqual(first.creative.story_version, 1)
        self.assertEqual(first.visual.style_version, 1)
        self.assertEqual(first.visual.story_id, first.creative.story_id)

    def test_invalid_planner_payload_blocks_formal_contract(self):
        with self.assertRaises(ContractValidationError):
            build_contract_bundle("完整故事。", {"title": "只有标题"})

    def test_contract_dictionary_keeps_version_links(self):
        bundle = build_contract_bundle("同一个完整故事。", self._planner())

        payload = bundle.to_dict()

        self.assertEqual(payload["status"], "visual_bible_review")
        self.assertEqual(payload["creative"]["story_id"], payload["visual"]["story_id"])
        self.assertEqual(payload["creative"]["story_version"], 1)
        self.assertEqual(payload["visual"]["style_version"], 1)

    def test_contract_round_trip_revalidates_story_and_style_links(self):
        first = build_contract_bundle("同一个完整故事。", self._planner())

        restored = contract_bundle_from_dict(first.to_dict())

        self.assertEqual(restored, first)

    @staticmethod
    def _planner():
        return {
            "title": "借光人",
            "genre": "古风幻想",
            "theme": "记忆与光明的代价",
            "protagonist_goal": "找回被抹去的亲人",
            "main_conflict": "城市以记忆换取光明",
            "causal_chain": ["发现异常", "追查真相", "熄灭月塔"],
            "ending": "城市迎来真正黎明",
            "episodes": [{"episode": 1, "summary": "发现异常", "evidence_quote": "同一个完整故事。"}],
            "must_keep": ["裂纹月灯"],
            "must_avoid": ["改写故事结局"],
            "visual": {
                "medium": "电影级国风厚涂动画",
                "era": "架空古代",
                "aspect_ratio": "9:16",
                "palette": ["靛青", "银白", "暗朱红"],
                "lighting": "冷月光与暖灯火形成叙事对照",
                "camera_language": "克制稳定",
                "character_rules": ["脸型固定"],
                "costume_rules": ["古代服装"],
                "prop_rules": ["材质固定"],
                "architecture_rules": ["木石结构"],
                "visual_motifs": ["裂纹月灯"],
                "prohibited_elements": ["现代车辆"],
            },
        }


if __name__ == "__main__":
    unittest.main()
