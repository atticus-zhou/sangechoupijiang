import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.comic_office.v2.asset_manifest import build_asset_manifest
from src.comic_office.v2.contracts import build_contract_bundle
from src.comic_office.v2.visual_review import VisualReviewResult
from src.image_generation import GeneratedImage
from src.llm.providers import LLMResponse, ModelConfig


STORY = "林昭提着裂纹月灯走进月塔，最终熄灭月塔。"


def bundle():
    return build_contract_bundle(STORY, {
        "title": "借月人",
        "genre": "古风幻想",
        "theme": "记忆与光明的代价",
        "protagonist_goal": "熄灭月塔",
        "main_conflict": "月塔燃烧记忆维持光明",
        "causal_chain": ["进入月塔", "发现真相", "熄灭月塔"],
        "ending": "林昭最终熄灭月塔",
        "episodes": [{"episode": 1, "summary": "熄灭月塔", "evidence_quote": "林昭提着裂纹月灯走进月塔"}],
        "visual": {
            "medium": "电影级国风厚涂动画",
            "era": "架空古代",
            "aspect_ratio": "9:16",
            "palette": ["靛青", "银白", "暗朱红"],
            "lighting": "冷月光与暖灯火对照",
            "camera_language": "克制稳定",
            "character_rules": ["脸型固定"],
            "costume_rules": ["古代窄袖长袍"],
            "prop_rules": ["裂纹位置固定"],
            "architecture_rules": ["木石结构"],
            "visual_motifs": ["裂纹月灯"],
            "prohibited_elements": ["现代车辆"],
        },
    })


def manifest():
    return build_asset_manifest(bundle(), [{
        "asset_type": "character",
        "name": "林昭",
        "evidence_quote": "林昭提着裂纹月灯走进月塔",
        "scene_ids": ["scene_01"],
        "story_purpose": "主角",
        "visual_locks": ["靛青窄袖长袍", "固定发髻"],
        "allowed_changes": ["表情", "姿势"],
    }])


def full_manifest():
    return build_asset_manifest(bundle(), [
        {
            "asset_type": "character",
            "name": "林昭",
            "evidence_quote": "林昭提着裂纹月灯走进月塔",
            "scene_ids": ["scene_01"],
            "story_purpose": "主角",
            "visual_locks": ["靛青窄袖长袍", "固定发髻"],
            "allowed_changes": ["表情", "姿势"],
        },
        {
            "asset_type": "prop",
            "name": "裂纹月灯",
            "evidence_quote": "裂纹月灯",
            "scene_ids": ["scene_01"],
            "story_purpose": "推动主角发现真相的核心证物",
            "visual_locks": ["银白裂纹", "古铜灯架"],
            "allowed_changes": ["发光强度"],
        },
        {
            "asset_type": "scene",
            "name": "月塔",
            "evidence_quote": "月塔",
            "scene_ids": ["scene_01"],
            "story_purpose": "高潮发生空间",
            "visual_locks": ["木石环形塔身", "中央灯芯"],
            "allowed_changes": ["光线"],
        },
    ])


class FakePromptProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def chat(self, messages, tools=None, tool_choice=None, response_format=None):
        self.calls.append(messages)
        return LLMResponse(content=self.responses.pop(0), model="fake/prompt", tokens_used=10)


def prompt_response(asset):
    prompts = []
    for kind in asset.planned_images:
        if asset.asset_type == "scene":
            purpose = {
                "wide": "广角空间图：展示空间边界、入口、出口、纵深和主要陈设。",
                "top_down": "俯视布局图：展示平面结构、走位区域和关键陈设位置。",
                "camera_angles": "关键机位参考：同一空间的远景、中景、低角度和特写背景机位。",
            }.get(kind, f"{kind}：展示空间结构。")
            background = "只展示空场景，空间结构清晰，保留真实空间环境背景。"
        else:
            purpose = f"{kind}：作为一致性参考，不表现剧情动作。"
            background = "纯白或近白干净背景。"
        prompts.append({
            "object_id": asset.asset_id,
            "image_kind": kind,
            "purpose": "identity_reference",
            "generator_prompt": (
                f"资产ID：{asset.asset_id}。资产名称：{asset.name}。{purpose}"
                f"故事用途：作为一致性参考，不表现剧情动作。视觉锁定：{asset.visual_locks[0]}。"
                "构图：主体居中，边缘完整，适合后续参考。"
                "光线：柔和工作室布光，结构和材质清晰。"
                f"电影级国风厚涂动画，架空古代，{background}"
            ),
            "negative_prompt": ["现代车辆", "文字水印"],
            "style_id": bundle().visual.style_id,
        })
    return json.dumps({"prompts": prompts}, ensure_ascii=False)


def review_result(status="pass", *, ready=True, revision_prompt=""):
    scores = {
        "identity_consistency": 90,
        "style_consistency": 90,
        "era_media": 90,
        "spatial_structure": 90,
        "asset_purity": 90,
        "anatomy": 90,
        "purpose_fit": 90,
    }
    if not ready:
        scores["identity_consistency"] = 62
    return VisualReviewResult(
        status=status,
        handoff_ready=ready,
        consistency_status="pass" if ready else "fail",
        scores=scores,
        issues=() if ready else ("脸型与基准不一致",),
        evidence=("符合视觉母版",) if ready else (),
        revision_prompt=revision_prompt,
        missing_dimensions=(),
        failed_dimensions=() if ready else ("identity_consistency",),
        reference_count=1 if ready else 0,
    )


class ComicV2ProductionTests(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_director_creates_one_specific_prompt_per_planned_image(self):
        from src.comic_office.v2.production import direct_asset_prompts

        item = manifest().items[0]
        provider = FakePromptProvider([prompt_response(item)])
        package = await direct_asset_prompts(
            bundle(),
            manifest(),
            ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=provider,
        )

        self.assertEqual(package.status, "ready")
        self.assertEqual({prompt.image_kind for prompt in package.prompts}, set(item.planned_images))
        self.assertTrue(all(prompt.object_id == item.asset_id for prompt in package.prompts))
        self.assertTrue(all(value.startswith("禁止") for prompt in package.prompts for value in prompt.negative_prompt))
        self.assertIn("只为这个资产", provider.calls[0][0].content)

    async def test_malformed_prompt_response_blocks_production_without_template_fallback(self):
        from src.comic_office.v2.production import ProductionError, direct_asset_prompts

        provider = FakePromptProvider(["not json", "still not json"])
        with self.assertRaisesRegex(ProductionError, "提示词"):
            await direct_asset_prompts(
                bundle(),
                manifest(),
                ModelConfig(provider="openai", model="fake", api_key="test"),
                llm=provider,
            )

    async def test_template_like_prompt_response_is_rejected_before_image_generation(self):
        from src.comic_office.v2.production import ProductionError, direct_asset_prompts

        item = manifest().items[0]
        prompts = []
        for kind in item.planned_images:
            prompts.append({
                "object_id": item.asset_id,
                "image_kind": kind,
                "purpose": "identity_reference",
                "generator_prompt": f"{item.name} {kind}，{item.visual_locks[0]}，纯白干净背景",
                "negative_prompt": ["文字水印"],
                "style_id": bundle().visual.style_id,
            })
        provider = FakePromptProvider([json.dumps({"prompts": prompts}, ensure_ascii=False)] * 2)

        with self.assertRaisesRegex(ProductionError, "资产ID|构图|光线|故事用途"):
            await direct_asset_prompts(
                bundle(),
                manifest(),
                ModelConfig(provider="openai", model="fake", api_key="test"),
                llm=provider,
            )

    async def test_scene_prompt_with_white_background_is_rejected_before_image_generation(self):
        from src.comic_office.v2.production import ProductionError, direct_asset_prompts

        items = full_manifest().items
        responses = [prompt_response(items[0]), prompt_response(items[1])]
        scene = items[2]
        bad_scene_prompts = []
        for kind in scene.planned_images:
            bad_scene_prompts.append({
                "object_id": scene.asset_id,
                "image_kind": kind,
                "purpose": "identity_reference",
                "generator_prompt": (
                    f"资产ID：{scene.asset_id}。资产名称：{scene.name}。{kind}。"
                    f"故事用途：作为空间参考。视觉锁定：{scene.visual_locks[0]}。"
                    "构图：主体居中，边缘完整。"
                    "光线：柔和工作室布光。"
                    "电影级国风厚涂动画，架空古代，纯白干净背景。"
                ),
                "negative_prompt": ["人物", "文字水印"],
                "style_id": bundle().visual.style_id,
            })
        bad_scene_response = json.dumps({"prompts": bad_scene_prompts}, ensure_ascii=False)
        responses.extend([bad_scene_response, bad_scene_response])
        provider = FakePromptProvider(responses)

        with self.assertRaisesRegex(ProductionError, "场景基础资产不能使用白底"):
            await direct_asset_prompts(
                bundle(),
                full_manifest(),
                ModelConfig(provider="openai", model="fake", api_key="test"),
                llm=provider,
            )

    async def test_asset_prompt_without_story_era_is_rejected_before_image_generation(self):
        from src.comic_office.v2.production import ProductionError, direct_asset_prompts

        item = manifest().items[0]
        prompts = []
        for kind in item.planned_images:
            prompts.append({
                "object_id": item.asset_id,
                "image_kind": kind,
                "purpose": "identity_reference",
                "generator_prompt": (
                    f"资产ID：{item.asset_id}。资产名称：{item.name}。{kind}。"
                    f"故事用途：作为一致性参考。视觉锁定：{item.visual_locks[0]}。"
                    "构图：角色居中，边缘完整。"
                    "光线：柔和工作室布光。"
                    "电影级国风厚涂动画，纯白干净背景。"
                ),
                "negative_prompt": ["文字水印"],
                "style_id": bundle().visual.style_id,
            })
        provider = FakePromptProvider([json.dumps({"prompts": prompts}, ensure_ascii=False)] * 2)

        with self.assertRaisesRegex(ProductionError, "故事时代"):
            await direct_asset_prompts(
                bundle(),
                manifest(),
                ModelConfig(provider="openai", model="fake", api_key="test"),
                llm=provider,
            )

    async def test_generation_establishes_baseline_then_reviews_next_image_against_it(self):
        from src.comic_office.v2.production import direct_asset_prompts, produce_asset_images

        item = manifest().items[0]
        package = await direct_asset_prompts(
            bundle(),
            manifest(),
            ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=FakePromptProvider([prompt_response(item)]),
        )
        review_requests = []

        def generator(config, prompt, output_dir, title):
            path = Path(output_dir) / f"{title}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-png")
            return GeneratedImage(title=title, prompt=prompt, path=str(path), provider="doubao", model="seedream")

        async def reviewer(request, *, baseline):
            review_requests.append((request, baseline))
            result = review_result()
            if baseline:
                return VisualReviewResult(**{**result.__dict__, "consistency_status": "baseline_established", "reference_count": 0})
            return result

        with tempfile.TemporaryDirectory() as tmp:
            result = await produce_asset_images(
                package,
                manifest(),
                bundle().visual,
                ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="test"),
                ModelConfig(provider="dashscope", model="qwen-vl", api_key="test"),
                Path(tmp),
                generator=generator,
                reviewer=reviewer,
                max_attempts=2,
            )

        self.assertTrue(result.production_ready)
        self.assertEqual(len(result.records), 2)
        self.assertTrue(result.records[0].is_identity_baseline)
        self.assertEqual(result.records[1].reference_image_ids, (result.records[0].image_id,))
        self.assertEqual(review_requests[0][0].reference_images, ())
        self.assertEqual(review_requests[1][0].reference_images, (result.records[0].path,))
        self.assertEqual(review_requests[0][0].production_role, "clean_character_identity_three_view")
        self.assertTrue(review_requests[0][0].clean_background_required)

    async def test_failed_review_retries_with_revision_but_keeps_asset_binding(self):
        from src.comic_office.v2.production import direct_asset_prompts, produce_asset_images

        item = manifest().items[0]
        package = await direct_asset_prompts(
            bundle(), manifest(), ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=FakePromptProvider([prompt_response(item)]),
        )
        generated_prompts = []
        review_count = 0

        def generator(config, prompt, output_dir, title):
            generated_prompts.append(prompt)
            path = Path(output_dir) / f"{title}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-png")
            return GeneratedImage(title=title, prompt=prompt, path=str(path), provider="doubao", model="seedream")

        async def reviewer(request, *, baseline):
            nonlocal review_count
            review_count += 1
            if review_count == 1:
                return review_result("fail", ready=False, revision_prompt="统一三视图脸型和发髻")
            result = review_result()
            if baseline:
                return VisualReviewResult(**{**result.__dict__, "consistency_status": "baseline_established", "reference_count": 0})
            return result

        with tempfile.TemporaryDirectory() as tmp:
            result = await produce_asset_images(
                package, manifest(), bundle().visual,
                ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="test"),
                ModelConfig(provider="dashscope", model="qwen-vl", api_key="test"),
                Path(tmp), generator=generator, reviewer=reviewer, max_attempts=2,
            )

        first = result.records[0]
        self.assertEqual(first.attempts, 2)
        self.assertEqual(first.asset_id, item.asset_id)
        self.assertIn("统一三视图脸型和发髻", generated_prompts[1])

    async def test_failed_visual_review_records_actionable_recovery_hint(self):
        from src.comic_office.v2.production import direct_asset_prompts, produce_asset_images

        item = manifest().items[0]
        package = await direct_asset_prompts(
            bundle(), manifest(), ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=FakePromptProvider([prompt_response(item)]),
        )

        def generator(config, prompt, output_dir, title):
            path = Path(output_dir) / f"{title}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-png")
            return GeneratedImage(title=title, prompt=prompt, path=str(path), provider="doubao", model="seedream")

        async def reviewer(request, *, baseline):
            return review_result("fail", ready=False, revision_prompt="统一人物身份")

        with tempfile.TemporaryDirectory() as tmp:
            result = await produce_asset_images(
                package, manifest(), bundle().visual,
                ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="test"),
                ModelConfig(provider="dashscope", model="qwen-vl", api_key="test"),
                Path(tmp), generator=generator, reviewer=reviewer, max_attempts=1,
            )

        self.assertFalse(result.production_ready)
        self.assertIn("action=regenerate_images", result.failures[0])
        self.assertEqual(result.records[0].review["recovery_action"], "regenerate_images")
        self.assertEqual(result.records[0].review["recovery_focus"], "images")

    async def test_generation_rejects_image_review_when_schema_gate_fails(self):
        from src.comic_office.v2.output_schemas import AgentOutputSchemaError
        from src.comic_office.v2.production import direct_asset_prompts, produce_asset_images

        item = manifest().items[0]
        package = await direct_asset_prompts(
            bundle(), manifest(), ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=FakePromptProvider([prompt_response(item)]),
        )

        def generator(config, prompt, output_dir, title):
            path = Path(output_dir) / f"{title}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-png")
            return GeneratedImage(title=title, prompt=prompt, path=str(path), provider="doubao", model="seedream")

        async def reviewer(request, *, baseline):
            return review_result()

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.comic_office.v2.production.validate_agent_output_schema",
                side_effect=AgentOutputSchemaError("image review schema rejected"),
            ) as gate:
                result = await produce_asset_images(
                    package, manifest(), bundle().visual,
                    ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="test"),
                    ModelConfig(provider="dashscope", model="qwen-vl", api_key="test"),
                    Path(tmp), generator=generator, reviewer=reviewer, max_attempts=1,
                )

        self.assertTrue(gate.called)
        self.assertFalse(result.production_ready)
        self.assertIn("image review schema rejected", "\n".join(result.failures))

    async def test_shot_prompt_cards_reference_approved_assets_without_planning_storyboard_images(self):
        from src.comic_office.v2.production import direct_asset_prompts, direct_shot_cards, prompt_package_from_dict

        assets = full_manifest()
        responses = [prompt_response(item) for item in assets.items]
        package = await direct_asset_prompts(
            bundle(), assets, ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=FakePromptProvider(responses),
        )
        by_type = {item.asset_type: item for item in assets.items}
        shot_response = json.dumps({"shots": [{
            "shot_id": "shot_01",
            "scene_id": "scene_01",
            "scene_asset_id": by_type["scene"].asset_id,
            "character_asset_ids": [by_type["character"].asset_id],
            "prop_asset_ids": [by_type["prop"].asset_id],
            "evidence_quote": "林昭提着裂纹月灯走进月塔",
            "story_beat": "林昭进入月塔并意识到必须作出选择",
            "action_chain": ["林昭推开塔门", "她举起裂纹月灯", "她望向塔心"],
            "performance_intent": "克制恐惧后转为决绝",
            "framing": "中近景平视",
            "camera_movement": "缓慢前推",
            "lighting": "冷月光压住灯火暖色",
            "dialogue": "林昭：到此为止。",
            "sound": "塔内风声与灯芯爆裂声",
            "retry_strategy": "优先修正脸型、月灯裂纹和动作顺序",
        }]}, ensure_ascii=False)

        completed = await direct_shot_cards(
            bundle(), assets, package,
            ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=FakePromptProvider([shot_response]),
        )

        self.assertEqual(len(completed.shots), 1)
        shot = completed.shots[0]
        self.assertEqual(set(shot.reference_asset_ids), {item.asset_id for item in assets.items})
        self.assertEqual(shot.evidence_quote, "林昭提着裂纹月灯走进月塔")
        self.assertIn("缓慢前推", shot.generator_prompt)
        self.assertFalse(any(prompt.image_kind in {"storyboard", "camera_motion"} for prompt in completed.prompts))
        self.assertEqual(prompt_package_from_dict(completed.to_dict()), completed)


if __name__ == "__main__":
    unittest.main()
