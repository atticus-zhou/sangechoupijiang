"""Purpose-specific prompts and executable shot cards for comic V2."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .asset_manifest import AssetPlan
from .contracts import VisualBible


@dataclass(frozen=True)
class PromptPlan:
    object_id: str
    image_kind: str
    purpose: str
    generator_prompt: str
    negative_prompt: tuple[str, ...]
    style_id: str

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
    first_frame = "、".join(reference_assets)
    action_text = "，随后".join(action_chain)
    dialogue = str(payload.get("dialogue") or "无台词，后期以表演和声音完成叙事").strip()
    sound = str(payload.get("sound") or "保留环境声和动作声音").strip()
    generator_prompt = (
        f"{_style_clause(visual)}。首帧参考：{first_frame}。"
        f"故事目的：{str(payload['story_beat']).strip()}。"
        f"动作链：{action_text}。表演意图：{str(payload['performance_intent']).strip()}。"
        f"摄影：{str(payload['framing']).strip()}，{str(payload['camera_movement']).strip()}。"
        f"灯光：{str(payload['lighting']).strip()}。台词：{dialogue}。声音：{sound}。"
        "严格继承参考资产的脸型、服装、道具形状和场景空间结构。"
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
        evidence_quote=str(payload.get("evidence_quote") or "").strip(),
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
