import unittest

from src.comic_office.v2.prompt_quality import audit_prompt_package


class ComicV2PromptQualityTests(unittest.TestCase):
    def test_ready_package_counts_clean_assets_and_director_shots(self):
        payload = {
            "prompts": [
                {
                    "object_id": "character_01",
                    "image_kind": "three_view",
                    "generator_prompt": "风格身份：style_01。资产ID：character_01。人物三视图，纯白或近白色干净背景。",
                    "negative_prompt": ["禁止剧情动作", "禁止剧情场景", "禁止文字、标签、编号和水印"],
                },
                {
                    "object_id": "prop_01",
                    "image_kind": "turnaround",
                    "generator_prompt": "风格身份：style_01。资产ID：prop_01。道具多角度转面，纯白或近白色干净背景。",
                    "negative_prompt": ["禁止人物手持或人物入镜", "禁止剧情现场", "禁止文字、标签、编号和水印"],
                },
                {
                    "object_id": "scene_01",
                    "image_kind": "wide",
                    "generator_prompt": "风格身份：style_01。资产ID：scene_01。广角空间图，只展示空场景，不发生剧情事件。",
                    "negative_prompt": ["禁止人物和人物互动", "禁止剧情事件", "禁止文字、标签、编号和水印"],
                },
            ],
            "shots": [
                {
                    "shot_id": "SHOT-01",
                    "generator_prompt": "首帧参考：character_01、prop_01、scene_01。故事目的：发现真相。动作链：举起月灯。表演意图：克制震惊。摄影：固定特写。灯光：冷月光。严格继承参考资产的脸型、服装、道具形状和场景空间结构。",
                    "negative_prompt": ["禁止资产身份漂移", "禁止动作顺序混乱", "禁止文字、标签、编号和水印"],
                }
            ],
        }

        result = audit_prompt_package(payload)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["clean_asset_prompt_count"], 3)
        self.assertEqual(result["director_prompt_count"], 1)
        self.assertEqual(result["issue_count"], 0)

    def test_flags_template_or_unreadable_prompt_language(self):
        result = audit_prompt_package({
            "prompts": [{
                "object_id": "character_01",
                "image_kind": "three_view",
                "generator_prompt": "人物图，不要乱画",
                "negative_prompt": ["不要文字"],
            }],
            "shots": [{
                "shot_id": "SHOT-01",
                "generator_prompt": "慢慢推进",
                "negative_prompt": ["不要漂移"],
            }],
        })

        self.assertEqual(result["status"], "needs_review")
        self.assertGreater(result["issue_count"], 0)
        messages = " ".join(item["message"] for item in result["issues"])
        self.assertIn("不要", messages)
        self.assertIn("导演字段", messages)


if __name__ == "__main__":
    unittest.main()
