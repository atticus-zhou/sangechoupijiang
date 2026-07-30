import unittest

from src.comic_office.v2.prompt_quality import audit_prompt_package


class ComicV2PromptQualityTests(unittest.TestCase):
    def test_ready_package_counts_clean_assets_and_director_shots(self):
        payload = {
            "prompts": [
                {
                    "object_id": "character_01",
                    "image_kind": "three_view",
                    "production_role": "clean_character_identity_three_view",
                    "clean_background_required": True,
                    "usage_contract": [
                        "基础资产图只建立角色身份参考，不负责讲述剧情。",
                        "本图种 three_view 用于锁定角色脸型、发型、体型、服装主色和年龄感。",
                    ],
                    "reference_policy": "人物资产用于后续镜头身份一致性参考。",
                    "generator_prompt": "风格身份：style_01。资产ID：character_01。人物三视图，纯白或近白色干净背景。",
                    "negative_prompt": ["禁止剧情动作", "禁止剧情场景", "禁止文字、标签、编号和水印"],
                },
                {
                    "object_id": "prop_01",
                    "image_kind": "turnaround",
                    "production_role": "clean_prop_turnaround_reference",
                    "clean_background_required": True,
                    "usage_contract": [
                        "基础资产图只建立道具身份参考，不负责讲述剧情。",
                        "本图种 turnaround 用于锁定道具轮廓、比例、材质和状态。",
                    ],
                    "reference_policy": "道具资产用于后续镜头物件一致性参考。",
                    "generator_prompt": "风格身份：style_01。资产ID：prop_01。道具多角度转面，纯白或近白色干净背景。",
                    "negative_prompt": ["禁止人物手持或人物入镜", "禁止剧情现场", "禁止文字、标签、编号和水印"],
                },
                {
                    "object_id": "scene_01",
                    "image_kind": "wide",
                    "production_role": "scene_spatial_wide_reference",
                    "clean_background_required": False,
                    "usage_contract": [
                        "基础资产图只建立空场景空间参考，不负责讲述剧情。",
                        "本图种 wide 用于锁定空间边界、入口出口、纵深、陈设和机位。",
                    ],
                    "reference_policy": "场景资产用于后续镜头空间一致性参考。",
                    "generator_prompt": "风格身份：style_01。资产ID：scene_01。广角空间图，只展示空场景，不发生剧情事件。",
                    "negative_prompt": ["禁止人物和人物互动", "禁止剧情事件", "禁止文字、标签、编号和水印"],
                },
            ],
            "shots": [
                {
                    "shot_id": "SHOT-01",
                    "generator_prompt": "\n".join([
                        "原文依据：林昭举起月灯。",
                        "镜头形式：固定特写；缓慢推进。",
                        "首帧参考：character_01、prop_01、scene_01。",
                        "参考资产：林昭（character_01）；月灯（prop_01）；月塔（scene_01）。",
                        "故事目的：发现真相。",
                        "动作链：举起月灯。",
                        "动作表演：克制震惊。",
                        "摄影：固定特写，缓慢推进。",
                        "灯光：冷月光。",
                        "台词：无台词。",
                        "声音：灯芯轻响。",
                        "连续性要求：严格继承参考资产的脸型、服装、道具形状和场景空间结构。",
                    ]),
                    "first_frame_reference_image": {
                        "image_id": "img_character_01_three_view",
                        "file": "character_01_three_view.png",
                        "asset_id": "character_01",
                    },
                    "reference_asset_chain": [
                        {"asset_id": "character_01", "asset_type": "character", "name": "林昭"},
                        {"asset_id": "prop_01", "asset_type": "prop", "name": "月灯"},
                        {"asset_id": "scene_01", "asset_type": "scene", "name": "月塔"},
                    ],
                    "negative_prompt": ["禁止资产身份漂移", "禁止动作顺序混乱", "禁止文字、标签、编号和水印"],
                }
            ],
        }

        result = audit_prompt_package(payload)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["clean_asset_prompt_count"], 3)
        self.assertEqual(result["director_prompt_count"], 1)
        self.assertEqual(result["issue_count"], 0)
        self.assertFalse(result["recovery"]["recoverable"])

    def test_flags_asset_prompt_without_usage_contract(self):
        result = audit_prompt_package({
            "prompts": [{
                "object_id": "character_01",
                "image_kind": "three_view",
                "production_role": "clean_character_identity_three_view",
                "clean_background_required": True,
                "generator_prompt": "风格身份：style_01。资产ID：character_01。人物三视图，纯白或近白色干净背景。",
                "negative_prompt": ["禁止剧情动作", "禁止剧情场景"],
            }],
            "shots": [],
        })

        self.assertEqual(result["status"], "needs_review")
        messages = " ".join(item["message"] for item in result["issues"])
        self.assertIn("usage_contract", messages)
        self.assertIn("reference_policy", messages)

    def test_flags_cross_asset_template_copy_before_handoff_benchmark(self):
        shared_generator = (
            "风格身份：style_01。资产ID：{asset_id}。人物三视图，纯白或近白色干净背景。"
            "青年修士，青灰色长袍，束发，冷静眼神，古风仙侠质感，正面侧面背面同页展示。"
            "服装材质清晰，脸型发型稳定，只建立角色身份参考。"
        )
        result = audit_prompt_package({
            "prompts": [
                {
                    "object_id": "character_01",
                    "image_kind": "three_view",
                    "production_role": "clean_character_identity_three_view",
                    "clean_background_required": True,
                    "usage_contract": ["基础资产图只建立角色身份参考，不负责讲述剧情。"],
                    "reference_policy": "人物资产用于后续镜头身份一致性参考。",
                    "generator_prompt": shared_generator.format(asset_id="character_01"),
                    "negative_prompt": ["禁止剧情动作", "禁止剧情场景", "禁止文字、标签、编号和水印"],
                },
                {
                    "object_id": "character_02",
                    "image_kind": "three_view",
                    "production_role": "clean_character_identity_three_view",
                    "clean_background_required": True,
                    "usage_contract": ["基础资产图只建立角色身份参考，不负责讲述剧情。"],
                    "reference_policy": "人物资产用于后续镜头身份一致性参考。",
                    "generator_prompt": shared_generator.format(asset_id="character_02"),
                    "negative_prompt": ["禁止剧情动作", "禁止剧情场景", "禁止文字、标签、编号和水印"],
                },
            ],
            "shots": [],
        })

        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["clean_asset_prompt_count"], 0)
        messages = " ".join(item["message"] for item in result["issues"])
        self.assertIn("疑似复制模板", messages)
        self.assertIn("重写专属视觉细节", messages)

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
        self.assertTrue(result["recovery"]["recoverable"])
        self.assertEqual(result["recovery"]["department"], "兵部 / 刑部")
        self.assertIn("重新生成专属提示词", result["recovery"]["next_action"])
        messages = " ".join(item["message"] for item in result["issues"])
        self.assertIn("不要", messages)
        self.assertIn("导演字段", messages)

    def test_flags_shot_prompt_without_first_frame_and_asset_chain(self):
        result = audit_prompt_package({
            "prompts": [],
            "shots": [{
                "shot_id": "SHOT-01",
                "generator_prompt": "原文依据：林昭停步。镜头形式：固定特写。首帧参考：character_01。参考资产：林昭（character_01）。故事目的：发现真相。动作链：停步、抬眼。动作表演：克制。摄影：固定特写。灯光：冷月光。台词：无。声音：环境声。连续性要求：严格继承参考资产身份。",
                "negative_prompt": ["禁止资产身份漂移", "禁止动作顺序混乱"],
            }],
        })

        self.assertEqual(result["status"], "needs_review")
        messages = " ".join(item["message"] for item in result["issues"])
        self.assertIn("首帧参考图片", messages)
        self.assertIn("reference_asset_chain", messages)


if __name__ == "__main__":
    unittest.main()
