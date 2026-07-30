import asyncio
import json
import unittest
from unittest.mock import patch

from src.comic_office.v2.asset_manifest import build_asset_manifest
from src.comic_office.v2.contracts import build_contract_bundle
from src.comic_office.v2.output_schemas import AgentOutputSchemaError
from src.comic_office.v2.prompt_director import (
    build_asset_prompt_plan,
    build_shot_card,
    parse_prompt_director_response,
)
from src.llm.providers import LLMResponse, ModelConfig


STORY = "林昭抱着裂纹月灯冲向中央月塔。她逆向转动控制环，最终熄灭月塔。"


def package_parts():
    bundle = build_contract_bundle(
        STORY,
        {
            "title": "借月人",
            "genre": "古风幻想",
            "theme": "记忆与光明的代价",
            "protagonist_goal": "熄灭月塔",
            "main_conflict": "守塔人阻止林昭",
            "causal_chain": ["进入月塔", "转动控制环", "月塔熄灭"],
            "ending": "林昭最终熄灭月塔",
            "episodes": [{"episode": 1, "summary": "熄灭月塔", "evidence_quote": "林昭抱着裂纹月灯冲向中央月塔"}],
            "visual": {
                "medium": "电影级国风厚涂动画",
                "era": "架空古代",
                "aspect_ratio": "9:16",
                "palette": ["靛青", "银白", "暗朱红"],
                "lighting": "冷银月光与暗红火光对照",
                "camera_language": "稳定构图，克制运镜",
                "character_rules": ["脸型、发髻和服装主色固定"],
                "costume_rules": ["古代窄袖长袍"],
                "prop_rules": ["裂纹位置固定"],
                "architecture_rules": ["石塔与古铜机械结构"],
                "visual_motifs": ["裂纹月灯", "逐层熄灭的灯火"],
                "prohibited_elements": ["现代服装", "现代机械", "可读文字"],
            },
        },
    )
    manifest = build_asset_manifest(bundle, [
        {
            "asset_type": "character",
            "name": "林昭",
            "evidence_quote": "林昭",
            "scene_ids": ["scene_01"],
            "story_purpose": "抱着月灯冲向塔心并熄灭月塔",
            "visual_locks": ["靛青窄袖长袍", "高发髻"],
            "allowed_changes": ["表情", "姿势"],
        },
        {
            "asset_type": "prop",
            "name": "裂纹月灯",
            "evidence_quote": "裂纹月灯",
            "scene_ids": ["scene_01"],
            "story_purpose": "承载亡者记忆并触发最终选择",
            "visual_locks": ["右上方固定弧形裂纹", "古铜框架"],
            "allowed_changes": ["亮度"],
        },
        {
            "asset_type": "scene",
            "name": "中央月塔",
            "evidence_quote": "中央月塔",
            "scene_ids": ["scene_01"],
            "story_purpose": "最终抉择发生地",
            "visual_locks": ["圆形外环", "中央控制环", "三条石桥"],
            "allowed_changes": ["灯火亮灭状态"],
        },
    ])
    by_type = {item.asset_type: item for item in manifest.items}
    return bundle.visual, by_type


def production_parts():
    bundle = build_contract_bundle(
        STORY,
        {
            "title": "借月人",
            "genre": "古风幻想",
            "theme": "记忆与光明的代价",
            "protagonist_goal": "熄灭月塔",
            "main_conflict": "守塔人阻止林昭",
            "causal_chain": ["进入月塔", "转动控制环", "月塔熄灭"],
            "ending": "林昭最终熄灭月塔",
            "episodes": [{"episode": 1, "summary": "熄灭月塔", "evidence_quote": STORY}],
            "visual": {
                "medium": "电影级国风厚涂动画",
                "era": "架空古代",
                "aspect_ratio": "9:16",
                "palette": ["靛青", "银白", "暗朱红"],
                "lighting": "冷银月光与暗红火光对照",
                "camera_language": "稳定构图，克制运镜",
                "character_rules": ["脸型、发髻和服装主色固定"],
                "costume_rules": ["古代窄袖长袍"],
                "prop_rules": ["裂纹位置固定"],
                "architecture_rules": ["石塔与古铜机械结构"],
                "visual_motifs": ["裂纹月灯", "逐层熄灭的灯火"],
                "prohibited_elements": ["现代服装", "现代机械", "可读文字"],
            },
        },
    )
    manifest = build_asset_manifest(bundle, [
        {
            "asset_type": "character",
            "name": "林昭",
            "evidence_quote": "林昭",
            "scene_ids": ["scene_01"],
            "story_purpose": "抱着月灯冲向塔心并熄灭月塔",
            "visual_locks": ["靛青窄袖长袍", "高发髻"],
            "allowed_changes": ["表情", "姿势"],
        },
        {
            "asset_type": "prop",
            "name": "裂纹月灯",
            "evidence_quote": "裂纹月灯",
            "scene_ids": ["scene_01"],
            "story_purpose": "承载亡者记忆并触发最终选择",
            "visual_locks": ["右上方固定弧形裂纹", "古铜框架"],
            "allowed_changes": ["亮度"],
        },
        {
            "asset_type": "scene",
            "name": "中央月塔",
            "evidence_quote": "中央月塔",
            "scene_ids": ["scene_01"],
            "story_purpose": "最终抉择发生地",
            "visual_locks": ["圆形外环", "中央控制环", "三条石桥"],
            "allowed_changes": ["灯火亮灭状态"],
        },
    ])
    return bundle, manifest


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)

    async def chat(self, messages, tools=None, tool_choice=None, response_format=None):
        return LLMResponse(content=self.responses.pop(0), model="fake/model", tokens_used=10)


class ComicV2PromptDirectorTests(unittest.TestCase):
    def test_base_character_prompt_is_readable_clean_and_identity_focused(self):
        visual, assets = package_parts()

        plan = build_asset_prompt_plan(assets["character"], visual, image_kind="three_view")

        self.assertEqual(plan.purpose, "identity_reference")
        self.assertEqual(plan.production_role, "clean_character_identity_three_view")
        self.assertTrue(plan.clean_background_required)
        self.assertTrue(plan.usage_contract)
        self.assertIn("基础资产", "；".join(plan.usage_contract))
        self.assertIn("不负责讲述剧情", "；".join(plan.usage_contract))
        self.assertIn("人物资产", plan.reference_policy)
        self.assertIn("资产ID", plan.generator_prompt)
        self.assertIn(assets["character"].asset_id, plan.generator_prompt)
        self.assertIn("纯白或近白色干净背景", plan.generator_prompt)
        self.assertIn("构图", plan.generator_prompt)
        self.assertIn("光线", plan.generator_prompt)
        self.assertIn("靛青窄袖长袍", plan.generator_prompt)
        self.assertIn("故事用途", plan.generator_prompt)
        self.assertNotIn("冲向", plan.generator_prompt)
        self.assertNotIn("熄灭月塔", plan.generator_prompt)
        self.assertNotIn("涓", plan.generator_prompt)
        self.assertTrue(all("不要" not in item for item in plan.negative_prompt))
        self.assertTrue(all(item.startswith("禁止") for item in plan.negative_prompt))

    def test_base_prop_prompt_is_clean_and_not_a_story_scene(self):
        visual, assets = package_parts()

        plan = build_asset_prompt_plan(assets["prop"], visual, image_kind="turnaround")

        self.assertEqual(plan.production_role, "clean_prop_turnaround_reference")
        self.assertTrue(plan.clean_background_required)
        self.assertIn("道具", "；".join(plan.usage_contract))
        self.assertIn("不负责讲述剧情", "；".join(plan.usage_contract))
        self.assertIn("道具资产", plan.reference_policy)
        self.assertIn("纯白或近白色干净背景", plan.generator_prompt)
        self.assertIn("右上方固定弧形裂纹", plan.generator_prompt)
        self.assertIn("材质", plan.generator_prompt)
        self.assertNotIn("亡者记忆", plan.generator_prompt)

    def test_scene_prompt_preserves_space_without_white_background(self):
        visual, assets = package_parts()

        plan = build_asset_prompt_plan(assets["scene"], visual, image_kind="top_down")

        self.assertEqual(plan.production_role, "scene_spatial_top_down_reference")
        self.assertFalse(plan.clean_background_required)
        self.assertIn("空场景", "；".join(plan.usage_contract))
        self.assertIn("不负责讲述剧情", "；".join(plan.usage_contract))
        self.assertIn("场景资产", plan.reference_policy)
        self.assertIn("俯视布局", plan.generator_prompt)
        self.assertIn("空间结构", plan.generator_prompt)
        self.assertIn("圆形外环", plan.generator_prompt)
        self.assertIn("中央控制环", plan.generator_prompt)
        self.assertNotIn("纯白或近白色干净背景", plan.generator_prompt)

    def test_two_asset_prompts_are_not_same_template_with_name_swap(self):
        visual, assets = package_parts()

        character = build_asset_prompt_plan(assets["character"], visual, image_kind="expression_sheet")
        prop = build_asset_prompt_plan(assets["prop"], visual, image_kind="state_sheet")

        self.assertIn("表情", character.generator_prompt)
        self.assertIn("状态变化", prop.generator_prompt)
        self.assertIn("脸型", character.generator_prompt)
        self.assertIn("形状", prop.generator_prompt)
        self.assertNotEqual(character.generator_prompt.replace("林昭", "裂纹月灯"), prop.generator_prompt)

    def test_shot_card_references_assets_and_contains_execution_fields(self):
        visual, assets = package_parts()
        payload = {
            "shot_id": "SHOT-01",
            "scene_id": "scene_01",
            "story_beat": "林昭抵达塔心并决定熄灭月塔",
            "action_chain": ["林昭走向控制环", "双手握住控制环", "逆向转动", "灯火逐层熄灭"],
            "performance_intent": "克制、坚定，不喊叫",
            "framing": "35mm 中广角，人物在画面下三分之一",
            "camera_movement": "从侧后方缓慢跟随并绕到正面",
            "lighting": "冷银顶光逐步熄灭，暗红余晖保留暖色",
            "dialogue": "林昭：够了。",
            "sound": "控制环摩擦声，随后全城寂静",
            "retry_strategy": "三人调度不稳定时只保留林昭与控制环，其余改为画外声音。",
            "acceptance_criteria": [
                "首帧必须引用林昭、裂纹月灯和中央月塔三项资产",
                "动作顺序必须保持走向控制环、握住、逆转、熄灭",
            ],
            "platform_note": "适合图生视频，先上传参考资产，再粘贴镜头提示词。",
        }

        card = build_shot_card(
            payload,
            characters=[assets["character"]],
            props=[assets["prop"]],
            scene=assets["scene"],
            visual=visual,
        )

        self.assertEqual(
            card.reference_asset_ids,
            (assets["character"].asset_id, assets["prop"].asset_id, assets["scene"].asset_id),
        )
        self.assertEqual(card.action_chain[-1], "灯火逐层熄灭")
        self.assertIn("首帧参考", card.generator_prompt)
        self.assertIn("原文依据", card.generator_prompt)
        self.assertIn("镜头形式", card.generator_prompt)
        self.assertIn("参考资产", card.generator_prompt)
        self.assertIn("林昭", card.generator_prompt)
        self.assertIn("裂纹月灯", card.generator_prompt)
        self.assertIn("中央月塔", card.generator_prompt)
        self.assertIn("故事目的", card.generator_prompt)
        self.assertIn("动作链", card.generator_prompt)
        self.assertIn("动作表演", card.generator_prompt)
        self.assertIn("摄影", card.generator_prompt)
        self.assertIn("台词", card.generator_prompt)
        self.assertIn("声音", card.generator_prompt)
        self.assertIn("连续性要求", card.generator_prompt)
        self.assertIn("靛青窄袖长袍", card.generator_prompt)
        self.assertIn("失败重试", card.retry_strategy_label)
        self.assertIn("首帧必须引用林昭", card.acceptance_criteria[0])
        self.assertIn("图生视频", card.platform_note)
        self.assertEqual(card.evidence_quote, "林昭抵达塔心并决定熄灭月塔")
        self.assertTrue(card.production_ready)

    def test_prompt_failure_has_no_silent_rule_fallback(self):
        result = parse_prompt_director_response("not-json")

        self.assertEqual(result.status, "prompt_failed")
        self.assertFalse(result.production_ready)
        self.assertEqual(result.prompts, ())

    def test_valid_prompt_response_keeps_negative_prompt_separate(self):
        result = parse_prompt_director_response(json.dumps({
            "prompts": [{
                "object_id": "character_1",
                "purpose": "identity_reference",
                "generator_prompt": "人物三视图，纯白背景",
                "negative_prompt": ["禁止文字", "禁止剧情动作"],
            }]
        }, ensure_ascii=False))

        self.assertEqual(result.status, "ready_for_prompt_review")
        self.assertTrue(result.production_ready)
        self.assertEqual(result.prompts[0].negative_prompt, ("禁止文字", "禁止剧情动作"))
        self.assertEqual(result.prompts[0].production_role, "clean_character_model_generated_reference")
        self.assertTrue(result.prompts[0].clean_background_required)
        self.assertIn("基础资产", "；".join(result.prompts[0].usage_contract))
        self.assertIn("不负责讲述剧情", "；".join(result.prompts[0].usage_contract))
        self.assertIn("人物资产", result.prompts[0].reference_policy)

    def test_model_inline_negative_prompt_is_moved_out_of_generator_prompt(self):
        result = parse_prompt_director_response(json.dumps({
            "prompts": [{
                "object_id": "character_1",
                "purpose": "identity_reference",
                "generator_prompt": "人物三视图，纯白背景，不要夸张表情。负面提示词：不要现代车辆，不要文字水印",
                "negative_prompt": ["不要脸型变化"],
            }]
        }, ensure_ascii=False))

        self.assertEqual(result.status, "ready_for_prompt_review")
        prompt = result.prompts[0]
        self.assertNotIn("负面提示词", prompt.generator_prompt)
        self.assertNotIn("不要", prompt.generator_prompt)
        self.assertIn("禁止夸张表情", prompt.generator_prompt)
        self.assertEqual(
            prompt.negative_prompt,
            ("禁止脸型变化", "禁止现代车辆", "禁止文字水印"),
        )


    def test_direct_asset_prompts_must_pass_agent_schema_gate(self):
        from src.comic_office.v2.production import ProductionError, direct_asset_prompts

        bundle, manifest = production_parts()
        response = {
            "prompts": [
                {
                    "object_id": manifest.items[0].asset_id,
                    "image_kind": image_kind,
                    "purpose": "identity_reference",
                    "generator_prompt": "placeholder",
                    "negative_prompt": ["禁止文字"],
                    "style_id": bundle.visual.style_id,
                }
                for image_kind in manifest.items[0].planned_images
            ]
        }

        async def run_case():
            await direct_asset_prompts(
                bundle,
                manifest,
                ModelConfig(provider="openai", model="fake", api_key="test"),
                llm=FakeProvider([json.dumps(response, ensure_ascii=False)] * 2),
            )

        with patch(
            "src.comic_office.v2.production.validate_agent_output_schema",
            side_effect=AgentOutputSchemaError("prompt schema rejected"),
        ):
            with self.assertRaisesRegex(ProductionError, "prompt schema rejected"):
                asyncio.run(run_case())

    def test_direct_shot_cards_must_pass_agent_schema_gate(self):
        from src.comic_office.v2.production import PromptPackage, ProductionError, direct_shot_cards

        bundle, manifest = production_parts()
        prompts = [
            build_asset_prompt_plan(asset, bundle.visual, image_kind=image_kind)
            for asset in manifest.items
            for image_kind in asset.planned_images
        ]
        package = PromptPackage(
            package_id="prompts_test",
            story_id=bundle.creative.story_id,
            story_version=bundle.creative.story_version,
            style_id=bundle.visual.style_id,
            style_version=bundle.visual.style_version,
            manifest_id=manifest.manifest_id,
            manifest_version=manifest.version,
            prompts=tuple(prompts),
        )

        async def run_case():
            await direct_shot_cards(
                bundle,
                manifest,
                package,
                ModelConfig(provider="openai", model="fake", api_key="test"),
                llm=FakeProvider([json.dumps({"shots": [{}]}, ensure_ascii=False)] * 2),
            )

        with patch(
            "src.comic_office.v2.production.validate_agent_output_schema",
            side_effect=AgentOutputSchemaError("shot schema rejected"),
        ):
            with self.assertRaisesRegex(ProductionError, "shot schema rejected"):
                asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
