"""Purpose-specific prompts and executable shot cards for comic V2."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .asset_manifest import AssetPlan
from .contracts import VisualBible


PROMPT_STRATEGY_VERSION = "comic_v2_prompt_director_v2"
PROMPT_STRATEGY_HASH = "asset_clean_base_and_director_shot_contract_2026_08_30"


@dataclass(frozen=True)
class PromptPlan:
    object_id: str
    image_kind: str
    purpose: str
    generator_prompt: str
    negative_prompt: tuple[str, ...]
    style_id: str
    production_role: str = ""
    clean_background_required: bool = False
    usage_contract: tuple[str, ...] = ()
    reference_policy: str = ""
    prompt_strategy_version: str = PROMPT_STRATEGY_VERSION
    prompt_strategy_hash: str = PROMPT_STRATEGY_HASH

    def render(self) -> str:
        negative = "；".join(self.negative_prompt)
        return f"{self.generator_prompt}\n负面提示词：{negative}" if negative else self.generator_prompt


@dataclass(frozen=True)
class PromptDirectorResult:
    status: str
    production_ready: bool
    prompts: tuple[PromptPlan, ...]
    error: str = ""


@dataclass(frozen=True)
class ShotCard:
    shot_id: str
    scene_id: str
    story_beat: str
    story_purpose: str
    reference_asset_ids: tuple[str, ...]
    action_chain: tuple[str, ...]
    performance_intent: str
    framing: str
    camera_movement: str
    lighting: str
    dialogue: str
    sound: str
    generator_prompt: str
    negative_prompt: tuple[str, ...]
    retry_strategy: str
    retry_strategy_label: str
    style_id: str
    evidence_quote: str = ""
    acceptance_criteria: tuple[str, ...] = ()
    platform_note: str = ""
    production_ready: bool = True
    prompt_strategy_version: str = PROMPT_STRATEGY_VERSION
    prompt_strategy_hash: str = PROMPT_STRATEGY_HASH


def build_asset_prompt_plan(
    asset: AssetPlan,
    visual: VisualBible,
    *,
    image_kind: str,
) -> PromptPlan:
    """Build a clean identity prompt for one planned asset image."""
    if image_kind not in asset.planned_images:
        raise ValueError(f"{image_kind} is not planned for {asset.asset_id}")

    style = _style_clause(visual)
    production_role = _asset_production_role(asset.asset_type, image_kind)
    clean_background_required = asset.asset_type in {"character", "prop"}
    locks = "；".join(asset.visual_locks)
    allowed = "、".join(asset.allowed_changes)
    identity = f"资产ID：{asset.asset_id}；资产名称：{asset.name}"
    boundary = "故事用途：作为后续镜头的一致性参考，只建立身份、形体、材质和空间规则，不表现剧情动作。"

    if asset.asset_type == "character":
        kind = {
            "three_view": "人物三视图：正面、侧面、背面，完整站姿，同一脸型、发型、体型和服装主色",
            "expression_sheet": "人物表情表：中性、震惊、愤怒、悲伤、克制、决绝，脸型和发型完全一致",
        }.get(image_kind, image_kind)
        prompt = (
            f"{style}。基础人物资产身份证，{identity}。{kind}。"
            f"视觉锁定：{locks}。允许变化：{allowed}。{boundary}"
            "构图：角色居中，比例完整，留出干净边距，适合后续抠图和一致性参考。"
            "光线：柔和工作室布光，面部结构清晰，服装纹理可辨。"
            "纯白或近白色干净背景，只展示人物基础设定。"
        )
        negative = (
            "禁止剧情动作",
            "禁止剧情场景",
            "禁止其他人物",
            "禁止文字、标签、编号和水印",
            "禁止脸型、发型和服装漂移",
        )
    elif asset.asset_type == "prop":
        kind = {
            "turnaround": "道具多角度转面：正面、侧面、三分之四视角和材质特写",
            "state_sheet": "道具状态变化图：静置、打开或关闭、完整或轻微磨损等基础状态",
        }.get(image_kind, image_kind)
        prompt = (
            f"{style}。基础道具资产身份证，{identity}。{kind}。"
            f"视觉锁定：{locks}。允许变化：{allowed}。{boundary}"
            "构图：单个道具居中展示，边缘完整，形状比例稳定。"
            "光线：柔和工作室布光，材质、磨损位置和结构细节清楚。"
            "纯白或近白色干净背景，只展示道具本体。"
        )
        negative = (
            "禁止人物手持或人物入镜",
            "禁止剧情现场",
            "禁止现代材料和现代包装",
            "禁止文字、标签、编号和水印",
            "禁止形状、比例、颜色和材质漂移",
        )
    elif asset.asset_type == "scene":
        kind = {
            "wide": "广角空间图：展示空间边界、入口、出口、纵深和主要陈设",
            "top_down": "俯视布局图：展示平面结构、走位区域和关键陈设位置",
            "camera_angles": "关键机位参考：同一空间的远景、中景、低角度和特写背景机位",
        }.get(image_kind, image_kind)
        prompt = (
            f"{style}。基础空场景资产身份证，{identity}。{kind}。"
            f"空间结构锁定：{locks}。允许变化：{allowed}。{boundary}"
            "构图：优先表达空间结构、入口出口、纵深关系和可拍摄机位。"
            "光线：沿用视觉母版光线，清楚标出明暗方向和关键陈设层次。"
            "只展示空场景，不发生剧情事件。"
        )
        negative = (
            "禁止人物和人物互动",
            "禁止剧情事件",
            "禁止改变空间结构",
            "禁止白底棚拍感",
            "禁止文字、标签、编号和水印",
        )
    else:
        raise ValueError(f"unsupported asset type: {asset.asset_type}")

    negative += tuple(_prohibition(item) for item in visual.prohibited_elements)
    return PromptPlan(
        object_id=asset.asset_id,
        image_kind=image_kind,
        purpose="identity_reference",
        generator_prompt=prompt,
        negative_prompt=_unique(negative),
        style_id=visual.style_id,
        production_role=production_role,
        clean_background_required=clean_background_required,
        usage_contract=_asset_usage_contract(asset, image_kind),
        reference_policy=_asset_reference_policy(asset),
    )


def build_shot_card(
    payload: dict[str, Any],
    *,
    characters: list[AssetPlan] | tuple[AssetPlan, ...],
    props: list[AssetPlan] | tuple[AssetPlan, ...],
    scene: AssetPlan,
    visual: VisualBible,
) -> ShotCard:
    """Build one executable narrative shot from approved identity assets."""
    required = (
        "shot_id",
        "scene_id",
        "story_beat",
        "action_chain",
        "performance_intent",
        "framing",
        "camera_movement",
        "lighting",
        "retry_strategy",
    )
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise ValueError(f"shot card missing fields: {', '.join(missing)}")
    if scene.asset_type != "scene":
        raise ValueError("scene reference must be a scene asset")
    if any(item.asset_type != "character" for item in characters):
        raise ValueError("character references must be character assets")
    if any(item.asset_type != "prop" for item in props):
        raise ValueError("prop references must be prop assets")

    reference_assets = tuple(
        [item.asset_id for item in characters]
        + [item.asset_id for item in props]
        + [scene.asset_id]
    )
    action_chain = _string_tuple(payload["action_chain"], "action_chain")
    story_purpose = str(payload.get("story_purpose") or payload["story_beat"]).strip()
    first_frame = "、".join(reference_assets)
    reference_summary = _shot_reference_summary(characters, props, scene)
    action_text = "，随后".join(action_chain)
    dialogue = str(payload.get("dialogue") or "无台词，后期以表演和声音完成叙事").strip()
    sound = str(payload.get("sound") or "保留环境声和动作声音").strip()
    evidence_quote = str(payload.get("evidence_quote") or payload["story_beat"]).strip()
    generator_prompt = "\n".join(
        [
            f"原文依据：{evidence_quote}",
            f"镜头形式：{str(payload['framing']).strip()}；{str(payload['camera_movement']).strip()}。",
            f"{_style_clause(visual)}。",
            f"首帧参考：{first_frame}。",
            f"参考资产：{reference_summary}。",
            f"故事目的：{story_purpose}。",
            f"动作链：{action_text}。",
            f"动作表演：{str(payload['performance_intent']).strip()}。",
            f"摄影：{str(payload['framing']).strip()}，{str(payload['camera_movement']).strip()}。",
            f"灯光：{str(payload['lighting']).strip()}。",
            f"台词：{dialogue}",
            f"声音：{sound}",
            "连续性要求：严格继承参考资产的脸型、发型、服装、道具形状、材质、场景空间结构和时代风格。",
        ]
    )
    negative = (
        "禁止资产身份漂移",
        "禁止无关人物和无关道具",
        "禁止动作顺序混乱",
        "禁止文字、标签、编号和水印",
    ) + tuple(_prohibition(item) for item in visual.prohibited_elements)
    retry = str(payload["retry_strategy"]).strip()
    acceptance_criteria = _shot_acceptance_criteria(payload, reference_assets)
    platform_note = str(
        payload.get("platform_note")
        or "适合图生视频首帧参考；先上传或绑定参考资产，再粘贴视频生成提示词；失败时优先按重试策略锁定资产身份和动作顺序。"
    ).strip()
    return ShotCard(
        shot_id=str(payload["shot_id"]).strip(),
        scene_id=str(payload["scene_id"]).strip(),
        story_beat=str(payload["story_beat"]).strip(),
        story_purpose=story_purpose,
        reference_asset_ids=reference_assets,
        action_chain=action_chain,
        performance_intent=str(payload["performance_intent"]).strip(),
        framing=str(payload["framing"]).strip(),
        camera_movement=str(payload["camera_movement"]).strip(),
        lighting=str(payload["lighting"]).strip(),
        dialogue=dialogue,
        sound=sound,
        generator_prompt=generator_prompt,
        negative_prompt=_unique(negative),
        retry_strategy=retry,
        retry_strategy_label=f"失败重试：{retry}",
        style_id=visual.style_id,
        evidence_quote=evidence_quote,
        acceptance_criteria=acceptance_criteria,
        platform_note=platform_note,
    )


def parse_prompt_director_response(text: str) -> PromptDirectorResult:
    """Parse model JSON without silently replacing invalid output with templates."""
    try:
        payload = json.loads((text or "").strip())
    except (TypeError, json.JSONDecodeError) as exc:
        return PromptDirectorResult(
            status="prompt_failed",
            production_ready=False,
            prompts=(),
            error=f"invalid prompt director JSON: {exc}",
        )
    if not isinstance(payload, dict) or not isinstance(payload.get("prompts"), list) or not payload["prompts"]:
        return PromptDirectorResult(
            status="prompt_failed",
            production_ready=False,
            prompts=(),
            error="prompt director response has no prompts",
        )
    prompts = []
    try:
        for item in payload["prompts"]:
            if not isinstance(item, dict):
                raise ValueError("prompt item must be an object")
            generator_prompt, inline_negative = _split_generator_prompt(
                str(item.get("generator_prompt") or "")
            )
            if not generator_prompt:
                raise ValueError("generator prompt is empty")
            negative = _string_tuple(item.get("negative_prompt") or (), "negative_prompt") + inline_negative
            prompts.append(PromptPlan(
                object_id=str(item.get("object_id") or "").strip(),
                image_kind=str(item.get("image_kind") or "model_generated").strip(),
                purpose=str(item.get("purpose") or "").strip(),
                generator_prompt=_normalize_generator_language(generator_prompt),
                negative_prompt=_unique(tuple(_prohibition(value) for value in negative)),
                style_id=str(item.get("style_id") or "").strip(),
                production_role=str(item.get("production_role") or _infer_production_role(item)).strip(),
                clean_background_required=_infer_clean_background_required(item),
                usage_contract=_infer_usage_contract(item),
                reference_policy=_infer_reference_policy(item),
                prompt_strategy_version=str(item.get("prompt_strategy_version") or PROMPT_STRATEGY_VERSION).strip(),
                prompt_strategy_hash=str(item.get("prompt_strategy_hash") or PROMPT_STRATEGY_HASH).strip(),
            ))
    except ValueError as exc:
        return PromptDirectorResult(
            status="prompt_failed",
            production_ready=False,
            prompts=(),
            error=str(exc),
        )
    return PromptDirectorResult(
        status="ready_for_prompt_review",
        production_ready=True,
        prompts=tuple(prompts),
    )


def _style_clause(visual: VisualBible) -> str:
    return (
        f"风格身份：{visual.style_id}，{visual.medium}，{visual.era}，"
        f"画面比例 {visual.aspect_ratio}，主色 {','.join(visual.palette)}，"
        f"光线 {visual.lighting}，镜头语言 {visual.camera_language}"
    )


def _asset_production_role(asset_type: str, image_kind: str) -> str:
    roles = {
        ("character", "three_view"): "clean_character_identity_three_view",
        ("character", "expression_sheet"): "clean_character_expression_library",
        ("prop", "turnaround"): "clean_prop_turnaround_reference",
        ("prop", "state_sheet"): "clean_prop_state_reference",
        ("scene", "wide"): "scene_spatial_wide_reference",
        ("scene", "top_down"): "scene_spatial_top_down_reference",
        ("scene", "camera_angles"): "scene_camera_angle_reference",
    }
    if (asset_type, image_kind) in roles:
        return roles[(asset_type, image_kind)]
    if asset_type in {"character", "prop"}:
        return f"clean_{asset_type}_{image_kind}_reference"
    return f"{asset_type}_{image_kind}_reference"


def _asset_usage_contract(asset: AssetPlan, image_kind: str) -> tuple[str, ...]:
    common = (
        "基础资产图只建立身份、形体、材质、空间和一致性参考，不负责讲述剧情。",
        "后续镜头必须引用本图作为参考资产，不得重新发明角色、道具或场景。",
    )
    if asset.asset_type == "character":
        return common + (
            f"本图种 {image_kind} 用于锁定同一角色的脸型、发型、体型、服装主色和年龄感。",
            "允许变化只限表情、姿势和镜头角度；禁止加入故事动作、其他人物和剧情现场。",
        )
    if asset.asset_type == "prop":
        return common + (
            f"本图种 {image_kind} 用于锁定单独道具的轮廓、比例、材质、磨损位置和可变化状态。",
            "允许变化只限开合、亮度、磨损或状态；禁止人物手持、剧情使用和现代化改造。",
        )
    if asset.asset_type == "scene":
        return common + (
            f"本图种 {image_kind} 用于锁定空场景的空间边界、入口出口、纵深、陈设和可拍机位。",
            "允许变化只限光线、天气、机位和局部陈设状态；禁止人物互动和剧情事件。",
        )
    return common


def _asset_reference_policy(asset: AssetPlan) -> str:
    if asset.asset_type == "character":
        return "人物资产必须优先作为脸型、发型、服装和年龄感参考；镜头生成时只继承身份，不继承白底背景。"
    if asset.asset_type == "prop":
        return "道具资产必须优先作为形状、材质、比例和状态参考；镜头生成时只继承道具身份，不继承白底背景。"
    if asset.asset_type == "scene":
        return "场景资产必须优先作为空间结构、动线和机位参考；镜头生成时继承空间关系，不把场景改成白底棚拍。"
    return "资产必须作为后续镜头的一致性参考，不得被下游重新改写。"


def _shot_reference_summary(
    characters: list[AssetPlan] | tuple[AssetPlan, ...],
    props: list[AssetPlan] | tuple[AssetPlan, ...],
    scene: AssetPlan,
) -> str:
    parts: list[str] = []
    for asset in [*characters, *props, scene]:
        locks = "、".join(asset.visual_locks[:3])
        suffix = f"，锁定：{locks}" if locks else ""
        parts.append(f"{asset.name}（{asset.asset_id}，{asset.asset_type}{suffix}）")
    return "；".join(parts)


def _infer_production_role(item: dict[str, Any]) -> str:
    object_id = str(item.get("object_id") or "")
    image_kind = str(item.get("image_kind") or "model_generated")
    if object_id.startswith("character_"):
        return _asset_production_role("character", image_kind)
    if object_id.startswith("prop_"):
        return _asset_production_role("prop", image_kind)
    if object_id.startswith("scene_"):
        return _asset_production_role("scene", image_kind)
    return "model_directed_asset_reference"


def _infer_clean_background_required(item: dict[str, Any]) -> bool:
    if "clean_background_required" in item:
        return bool(item.get("clean_background_required"))
    object_id = str(item.get("object_id") or "")
    return object_id.startswith("character_") or object_id.startswith("prop_")


def _infer_usage_contract(item: dict[str, Any]) -> tuple[str, ...]:
    raw = item.get("usage_contract") or item.get("asset_contract") or ()
    if isinstance(raw, str):
        raw_values = (raw,)
    elif isinstance(raw, (list, tuple)):
        raw_values = tuple(str(value).strip() for value in raw if str(value).strip())
    else:
        raw_values = ()
    if raw_values:
        return _unique(raw_values)
    object_id = str(item.get("object_id") or "")
    image_kind = str(item.get("image_kind") or "model_generated")
    if object_id.startswith("character_"):
        return (
            "基础资产图只建立角色身份参考，不负责讲述剧情。",
            f"本图种 {image_kind} 用于锁定角色脸型、发型、体型、服装主色和年龄感。",
            "禁止加入故事动作、其他人物和剧情现场。",
        )
    if object_id.startswith("prop_"):
        return (
            "基础资产图只建立道具身份参考，不负责讲述剧情。",
            f"本图种 {image_kind} 用于锁定道具轮廓、比例、材质和状态。",
            "禁止人物手持、剧情使用和现代化改造。",
        )
    if object_id.startswith("scene_"):
        return (
            "基础资产图只建立空场景空间参考，不负责讲述剧情。",
            f"本图种 {image_kind} 用于锁定空间边界、入口出口、纵深、陈设和机位。",
            "禁止人物互动和剧情事件。",
        )
    return ("基础资产图只建立一致性参考，不负责讲述剧情。",)


def _infer_reference_policy(item: dict[str, Any]) -> str:
    raw = str(item.get("reference_policy") or "").strip()
    if raw:
        return raw
    object_id = str(item.get("object_id") or "")
    if object_id.startswith("character_"):
        return "人物资产用于后续镜头身份一致性参考；镜头生成时继承脸型、发型、服装和年龄感。"
    if object_id.startswith("prop_"):
        return "道具资产用于后续镜头物件一致性参考；镜头生成时继承形状、材质、比例和状态。"
    if object_id.startswith("scene_"):
        return "场景资产用于后续镜头空间一致性参考；镜头生成时继承空间结构、动线和机位。"
    return "资产用于后续镜头一致性参考。"


def _prohibition(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^(不要|不得|避免|禁止)", "", text).strip(" ：:，,。；;")
    return f"禁止{text}" if text else ""


def _split_generator_prompt(value: str) -> tuple[str, tuple[str, ...]]:
    text = str(value or "").strip()
    markers = ("负面提示词：", "负面提示词:", "negative prompt:", "Negative prompt:")
    for marker in markers:
        if marker in text:
            body, negative = text.split(marker, 1)
            return body.strip(), _inline_negative_terms(negative)
    return text, ()


def _inline_negative_terms(value: str) -> tuple[str, ...]:
    normalized = re.sub(r"[，,；;、\n]+", "|", str(value or ""))
    return tuple(part.strip() for part in normalized.split("|") if part.strip())


def _normalize_generator_language(value: str) -> str:
    text = str(value or "").strip()
    return text.replace("不要", "禁止").replace("不得", "禁止")


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be an array")
    result = tuple(str(item).strip() for item in value if str(item).strip())
    if not result:
        raise ValueError(f"{label} must contain at least one item")
    return result


def _shot_acceptance_criteria(payload: dict[str, Any], reference_asset_ids: tuple[str, ...]) -> tuple[str, ...]:
    raw = payload.get("acceptance_criteria") or payload.get("acceptance") or ()
    supplied = _string_tuple(raw, "acceptance_criteria") if raw else ()
    defaults = (
        f"首帧和后续画面必须引用已批准资产：{'、'.join(reference_asset_ids)}。",
        "人物脸型、服装主色、道具形状和场景空间结构必须与资产身份证一致。",
        "动作链必须按顺序执行，故事目的和情绪方向不能改变。",
    )
    return _unique(supplied + defaults)


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
