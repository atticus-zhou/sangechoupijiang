"""Prompt directing, image generation, and reference-aware review for comic V2."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.image_generation import GeneratedImage, generate_doubao_image, is_image_generation_config
from src.llm.providers import LLMFactory, LLMMessage, ModelConfig
from src.llm.robust_json import parse_json_object

from .asset_manifest import AssetManifest, AssetPlan
from .contracts import ContractBundle, VisualBible
from .prompt_director import PromptPlan, ShotCard, build_shot_card, parse_prompt_director_response
from .visual_review import (
    VisualReviewRequest,
    VisualReviewResult,
    build_visual_review_request,
    normalize_baseline_review,
    normalize_visual_review,
)


class ProductionError(RuntimeError):
    """Raised when a formal production stage cannot produce usable output."""


@dataclass(frozen=True)
class PromptPackage:
    package_id: str
    story_id: str
    story_version: int
    style_id: str
    style_version: int
    manifest_id: str
    manifest_version: int
    prompts: tuple[PromptPlan, ...]
    status: str = "ready"
    shots: tuple[ShotCard, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImageRecord:
    image_id: str
    asset_id: str
    image_kind: str
    prompt_hash: str
    path: str
    provider: str
    model: str
    attempts: int
    status: str
    is_identity_baseline: bool
    reference_image_ids: tuple[str, ...]
    story_id: str
    story_version: int
    style_id: str
    style_version: int
    manifest_version: int
    review: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImageProductionResult:
    status: str
    production_ready: bool
    records: tuple[ImageRecord, ...]
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def prompt_package_from_dict(payload: dict[str, Any]) -> PromptPackage:
    """Restore a persisted prompt package with tuple fields intact."""
    if not isinstance(payload, dict):
        raise ProductionError("提示词包必须是对象")
    prompts = tuple(
        PromptPlan(
            object_id=str(item.get("object_id") or ""),
            image_kind=str(item.get("image_kind") or ""),
            purpose=str(item.get("purpose") or ""),
            generator_prompt=str(item.get("generator_prompt") or ""),
            negative_prompt=tuple(item.get("negative_prompt") or ()),
            style_id=str(item.get("style_id") or ""),
        )
        for item in (payload.get("prompts") or [])
    )
    shots = tuple(
        ShotCard(
            shot_id=str(item.get("shot_id") or ""),
            scene_id=str(item.get("scene_id") or ""),
            story_beat=str(item.get("story_beat") or ""),
            reference_asset_ids=tuple(item.get("reference_asset_ids") or ()),
            action_chain=tuple(item.get("action_chain") or ()),
            performance_intent=str(item.get("performance_intent") or ""),
            framing=str(item.get("framing") or ""),
            camera_movement=str(item.get("camera_movement") or ""),
            lighting=str(item.get("lighting") or ""),
            dialogue=str(item.get("dialogue") or ""),
            sound=str(item.get("sound") or ""),
            generator_prompt=str(item.get("generator_prompt") or ""),
            negative_prompt=tuple(item.get("negative_prompt") or ()),
            retry_strategy=str(item.get("retry_strategy") or ""),
            retry_strategy_label=str(item.get("retry_strategy_label") or ""),
            style_id=str(item.get("style_id") or ""),
            evidence_quote=str(item.get("evidence_quote") or ""),
            production_ready=bool(item.get("production_ready", True)),
        )
        for item in (payload.get("shots") or [])
    )
    return PromptPackage(
        package_id=str(payload.get("package_id") or ""),
        story_id=str(payload.get("story_id") or ""),
        story_version=int(payload.get("story_version") or 0),
        style_id=str(payload.get("style_id") or ""),
        style_version=int(payload.get("style_version") or 0),
        manifest_id=str(payload.get("manifest_id") or ""),
        manifest_version=int(payload.get("manifest_version") or 0),
        prompts=prompts,
        status=str(payload.get("status") or "ready"),
        shots=shots,
    )


async def direct_asset_prompts(
    bundle: ContractBundle,
    manifest: AssetManifest,
    model_config: ModelConfig,
    *,
    llm=None,
) -> PromptPackage:
    """Generate purpose-specific prompts one asset at a time through the configured model."""
    if not _text_model_usable(model_config):
        raise ProductionError("工部文本模型未配置，无法生成逐项提示词")
    provider = llm or LLMFactory.create(model_config)
    prompts: list[PromptPlan] = []
    for asset in manifest.items:
        parsed = None
        last_error = ""
        for _attempt in range(2):
            response = await provider.chat(
                [
                    LLMMessage(role="system", content=_prompt_director_system_prompt(asset)),
                    LLMMessage(role="user", content=_prompt_director_user_prompt(bundle, manifest, asset)),
                ],
                response_format={"type": "json_object"},
            )
            raw = (response.content or "").strip()
            if not raw or raw.startswith("[API错误]"):
                last_error = raw.removeprefix("[API错误]").strip() or "模型返回空内容"
                continue
            parsed = parse_prompt_director_response(raw)
            if not parsed.production_ready:
                last_error = parsed.error
                continue
            try:
                _validate_asset_prompt_set(asset, bundle.visual, parsed.prompts)
            except ProductionError as exc:
                last_error = str(exc)
                parsed = None
                continue
            break
        if parsed is None or not parsed.production_ready:
            raise ProductionError(f"{asset.name} 的提示词生成失败：{last_error or '结构不完整'}")
        prompts.extend(_ordered_prompts(asset, parsed.prompts))
    package_raw = json.dumps(
        {
            "story_id": bundle.creative.story_id,
            "style_id": bundle.visual.style_id,
            "manifest_hash": manifest.manifest_hash,
            "prompts": [asdict(prompt) for prompt in prompts],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    package_id = f"prompts_{hashlib.sha256(package_raw.encode('utf-8')).hexdigest()[:12]}"
    return PromptPackage(
        package_id=package_id,
        story_id=bundle.creative.story_id,
        story_version=bundle.creative.story_version,
        style_id=bundle.visual.style_id,
        style_version=bundle.visual.style_version,
        manifest_id=manifest.manifest_id,
        manifest_version=manifest.version,
        prompts=tuple(prompts),
    )


async def direct_shot_cards(
    bundle: ContractBundle,
    manifest: AssetManifest,
    prompt_package: PromptPackage,
    model_config: ModelConfig,
    *,
    llm=None,
) -> PromptPackage:
    """Create executable shot/video prompt cards without generating storyboard images."""
    if not _text_model_usable(model_config):
        raise ProductionError("兵部文本模型未配置，无法生成镜头提示词卡")
    _validate_package_binding(prompt_package, manifest, bundle.visual)
    provider = llm or LLMFactory.create(model_config)
    last_error = ""
    for _attempt in range(2):
        response = await provider.chat(
            [
                LLMMessage(role="system", content=_shot_director_system_prompt()),
                LLMMessage(role="user", content=_shot_director_user_prompt(bundle, manifest)),
            ],
            response_format={"type": "json_object"},
        )
        raw = (response.content or "").strip()
        if not raw or raw.startswith("[API错误]"):
            last_error = raw.removeprefix("[API错误]").strip() or "模型返回空内容"
            continue
        payload = parse_json_object(raw)
        shot_payloads = payload.get("shots") if isinstance(payload, dict) else None
        if not isinstance(shot_payloads, list) or not shot_payloads:
            last_error = "兵部没有返回镜头提示词卡"
            continue
        try:
            shots = tuple(_build_model_shot(item, bundle, manifest) for item in shot_payloads)
            if len({shot.shot_id for shot in shots}) != len(shots):
                raise ProductionError("镜头编号重复")
        except (KeyError, TypeError, ValueError, ProductionError) as exc:
            last_error = str(exc)
            continue
        return replace(prompt_package, shots=shots)
    raise ProductionError(f"镜头提示词生成失败：{last_error or '结构不完整'}")


async def produce_asset_images(
    prompt_package: PromptPackage,
    manifest: AssetManifest,
    visual: VisualBible,
    image_config: ModelConfig,
    review_config: ModelConfig,
    output_dir: Path,
    *,
    generator: Callable[..., GeneratedImage] = generate_doubao_image,
    reviewer: Callable[..., Awaitable[VisualReviewResult]] | None = None,
    max_attempts: int = 2,
) -> ImageProductionResult:
    """Generate every planned base asset and promote only reference-reviewed images."""
    if not is_image_generation_config(image_config):
        raise ProductionError("工部生图模型不是受支持的图片生成模型")
    if not _vision_model_usable(review_config):
        raise ProductionError("刑部多模态模型未配置，无法执行跨图质检")
    _validate_package_binding(prompt_package, manifest, visual)
    review_image = reviewer or (
        lambda request, *, baseline: run_visual_review(review_config, request, baseline=baseline)
    )
    output_dir = Path(output_dir)
    records: list[ImageRecord] = []
    failures: list[str] = []
    approved_by_asset: dict[str, list[ImageRecord]] = {}
    prompt_lookup = {(prompt.object_id, prompt.image_kind): prompt for prompt in prompt_package.prompts}

    for asset in manifest.items:
        for kind_index, image_kind in enumerate(asset.planned_images):
            plan = prompt_lookup[(asset.asset_id, image_kind)]
            is_baseline = kind_index == 0
            approved = approved_by_asset.get(asset.asset_id, [])
            if not is_baseline and not approved:
                failures.append(f"{asset.asset_id}/{image_kind}: 缺少已通过的身份基准图")
                continue
            references = tuple(record.path for record in approved[:1])
            reference_ids = tuple(record.image_id for record in approved[:1])
            previous = approved[-1].path if len(approved) > 1 else ""
            current_prompt = _render_attempt_prompt(plan)
            final_image = None
            final_review = None
            attempts = 0
            for attempt in range(1, max(1, int(max_attempts)) + 1):
                attempts = attempt
                title = f"{asset.asset_id}_{image_kind}"
                try:
                    generated = await asyncio.to_thread(
                        generator,
                        image_config,
                        current_prompt,
                        output_dir,
                        title,
                    )
                except Exception as exc:
                    if attempt >= max_attempts:
                        failures.append(f"{asset.asset_id}/{image_kind}: 生图失败 {exc}")
                    continue
                final_image = generated
                request = build_visual_review_request(
                    generated.path,
                    references,
                    previous_accepted_image=previous,
                    visual_bible_summary=_visual_summary(visual),
                    acceptance_criteria=_acceptance_criteria(asset, image_kind),
                )
                final_review = await review_image(request, baseline=is_baseline)
                if final_review.handoff_ready:
                    break
                if attempt < max_attempts:
                    current_prompt = _render_attempt_prompt(plan, final_review.revision_prompt or "修正质检问题")
            if final_image is None or final_review is None:
                continue
            status = "approved" if final_review.handoff_ready else "needs_human_review"
            if status != "approved":
                failures.append(f"{asset.asset_id}/{image_kind}: 视觉质检未通过")
            record = ImageRecord(
                image_id=f"img_{asset.asset_id}_{image_kind}",
                asset_id=asset.asset_id,
                image_kind=image_kind,
                prompt_hash=hashlib.sha256(current_prompt.encode("utf-8")).hexdigest(),
                path=str(final_image.path),
                provider=final_image.provider,
                model=final_image.model,
                attempts=attempts,
                status=status,
                is_identity_baseline=is_baseline,
                reference_image_ids=reference_ids,
                story_id=prompt_package.story_id,
                story_version=prompt_package.story_version,
                style_id=prompt_package.style_id,
                style_version=prompt_package.style_version,
                manifest_version=prompt_package.manifest_version,
                review=asdict(final_review),
            )
            records.append(record)
            if status == "approved":
                approved_by_asset.setdefault(asset.asset_id, []).append(record)

    ready = len(records) == len(prompt_package.prompts) and not failures and all(
        record.status == "approved" for record in records
    )
    return ImageProductionResult(
        status="ready_for_delivery" if ready else "needs_human_review",
        production_ready=ready,
        records=tuple(records),
        failures=tuple(failures),
    )


async def run_visual_review(
    config: ModelConfig,
    request: VisualReviewRequest,
    *,
    baseline: bool,
    llm=None,
) -> VisualReviewResult:
    provider = llm or LLMFactory.create(config)
    images = [base64.b64encode(Path(path).read_bytes()).decode("ascii") for path in request.image_paths]
    response = await provider.chat_with_vision(
        text=request.instruction,
        images=images,
        system="你是AI漫剧制片办公室的刑部视觉质检官，只依据所给图片、视觉母版和验收标准判断。",
    )
    raw = (response.content or "").strip()
    payload = {} if raw.startswith("[API错误]") else parse_json_object(raw)
    if baseline:
        return normalize_baseline_review(payload, request)
    return normalize_visual_review(payload, request)


def _prompt_director_system_prompt(asset: AssetPlan) -> str:
    return "\n".join(
        [
            "你是 AI 漫剧制片办公室的工部提示词导演。",
            "只为这个资产及其计划图组写专属生图提示词，禁止套用同一段模板替换名字。",
            "基础人物和道具图用于建立身份，不讲剧情；人物和道具使用纯白或近白干净背景。",
            "基础场景图必须是空场景并体现真实空间，禁止白底。",
            f"本次资产类型：{asset.asset_type}；计划图组：{','.join(asset.planned_images)}。",
            "每个计划图种必须恰好返回一项，object_id、image_kind、style_id 必须与输入一致。",
            "negative_prompt 单独列数组，使用可执行名词短语；系统会统一加上“禁止”。",
            "只输出 JSON：{\"prompts\":[{\"object_id\":\"\",\"image_kind\":\"\",\"purpose\":\"identity_reference\",\"generator_prompt\":\"\",\"negative_prompt\":[\"\"],\"style_id\":\"\"}]}。",
        ]
    )


def _shot_director_system_prompt() -> str:
    return "\n".join(
        [
            "你是 AI 漫剧制片办公室的兵部导演。",
            "把确认故事拆成可直接交给视频生成平台的镜头提示词卡，不生成分镜图和运镜图。",
            "每个镜头必须引用已审核资产ID，并用 evidence_quote 逐字引用确认故事中的依据。",
            "动作链按发生顺序写清，表演意图、景别、机位或运动、灯光、台词和声音必须随剧情变化，禁止批量套同一模板。",
            "固定镜头也要明确写 camera_movement 为固定机位；有对白时逐字写 dialogue。",
            "只输出 JSON 对象，根字段 shots。每项字段：shot_id, scene_id, scene_asset_id, character_asset_ids, prop_asset_ids, evidence_quote, story_beat, action_chain, performance_intent, framing, camera_movement, lighting, dialogue, sound, retry_strategy。",
            "禁止 Markdown 和额外解释。",
        ]
    )


def _shot_director_user_prompt(bundle: ContractBundle, manifest: AssetManifest) -> str:
    inventory = [
        {
            "asset_id": item.asset_id,
            "asset_type": item.asset_type,
            "name": item.name,
            "scene_ids": list(item.evidence.scene_ids),
            "story_purpose": item.story_purpose,
        }
        for item in manifest.items
    ]
    return "\n".join(
        [
            "[确认故事]",
            bundle.creative.source_story,
            "[已审核资产ID]",
            json.dumps(inventory, ensure_ascii=False),
            "[视觉母版]",
            json.dumps(asdict(bundle.visual), ensure_ascii=False),
            "请按故事真实动作顺序生成完整镜头提示词卡。",
        ]
    )


def _build_model_shot(payload: dict[str, Any], bundle: ContractBundle, manifest: AssetManifest) -> ShotCard:
    if not isinstance(payload, dict):
        raise ProductionError("镜头提示词卡必须是对象")
    evidence = str(payload.get("evidence_quote") or "").strip()
    if not evidence or evidence not in bundle.creative.source_story:
        raise ProductionError("镜头提示词卡缺少确认故事中的逐字证据")
    by_id = {item.asset_id: item for item in manifest.items}
    scene_id = str(payload.get("scene_asset_id") or "").strip()
    if scene_id not in by_id or by_id[scene_id].asset_type != "scene":
        raise ProductionError("镜头引用了无效场景资产")
    character_ids = tuple(str(value).strip() for value in payload.get("character_asset_ids") or [])
    prop_ids = tuple(str(value).strip() for value in payload.get("prop_asset_ids") or [])
    if any(value not in by_id or by_id[value].asset_type != "character" for value in character_ids):
        raise ProductionError("镜头引用了无效人物资产")
    if any(value not in by_id or by_id[value].asset_type != "prop" for value in prop_ids):
        raise ProductionError("镜头引用了无效道具资产")
    return build_shot_card(
        payload,
        characters=[by_id[value] for value in character_ids],
        props=[by_id[value] for value in prop_ids],
        scene=by_id[scene_id],
        visual=bundle.visual,
    )


def _prompt_director_user_prompt(bundle: ContractBundle, manifest: AssetManifest, asset: AssetPlan) -> str:
    return "\n".join(
        [
            f"故事ID：{bundle.creative.story_id} v{bundle.creative.story_version}",
            f"风格ID：{bundle.visual.style_id} v{bundle.visual.style_version}",
            f"资产清单版本：{manifest.version}",
            f"资产：{json.dumps(asdict(asset), ensure_ascii=False)}",
            f"视觉母版：{json.dumps(asdict(bundle.visual), ensure_ascii=False)}",
            "请写出每一种计划图对应的完整、可直接执行的中文提示词。",
        ]
    )


def _validate_asset_prompt_set(
    asset: AssetPlan,
    visual: VisualBible,
    prompts: tuple[PromptPlan, ...],
) -> None:
    expected = set(asset.planned_images)
    actual = {prompt.image_kind for prompt in prompts}
    if actual != expected or len(prompts) != len(expected):
        raise ProductionError(f"提示词图组不完整，期望 {sorted(expected)}，实际 {sorted(actual)}")
    for prompt in prompts:
        if prompt.object_id != asset.asset_id or prompt.style_id != visual.style_id:
            raise ProductionError("提示词的资产或风格绑定错误")
        if asset.name not in prompt.generator_prompt:
            raise ProductionError("提示词没有写明资产名称")
        if not any(lock in prompt.generator_prompt for lock in asset.visual_locks):
            raise ProductionError("提示词没有落实资产视觉锁定")
        if asset.asset_type in {"character", "prop"} and "白" not in prompt.generator_prompt:
            raise ProductionError("人物和道具基础资产必须使用白色干净背景")


def _ordered_prompts(asset: AssetPlan, prompts: tuple[PromptPlan, ...]) -> tuple[PromptPlan, ...]:
    by_kind = {prompt.image_kind: prompt for prompt in prompts}
    return tuple(by_kind[kind] for kind in asset.planned_images)


def _validate_package_binding(package: PromptPackage, manifest: AssetManifest, visual: VisualBible) -> None:
    if package.manifest_id != manifest.manifest_id or package.manifest_version != manifest.version:
        raise ProductionError("提示词包属于另一版资产清单")
    if package.style_id != visual.style_id or package.style_version != visual.style_version:
        raise ProductionError("提示词包属于另一版视觉母版")
    expected = {(item.asset_id, kind) for item in manifest.items for kind in item.planned_images}
    actual = {(prompt.object_id, prompt.image_kind) for prompt in package.prompts}
    if actual != expected:
        raise ProductionError("提示词包没有覆盖全部计划图片")


def _render_attempt_prompt(plan: PromptPlan, revision: str = "") -> str:
    body = plan.generator_prompt.strip()
    if revision.strip():
        body = f"{body}\n本次质检修正要求：{revision.strip()}。保持资产ID与视觉锁定不变。"
    negative = "；".join(plan.negative_prompt)
    return f"{body}\n负面提示词：{negative}" if negative else body


def _visual_summary(visual: VisualBible) -> str:
    return "；".join(
        [
            visual.medium,
            visual.era,
            f"比例 {visual.aspect_ratio}",
            f"色彩 {','.join(visual.palette)}",
            f"光线 {visual.lighting}",
            f"镜头 {visual.camera_language}",
        ]
    )


def _acceptance_criteria(asset: AssetPlan, image_kind: str) -> tuple[str, ...]:
    criteria = [f"正确呈现 {asset.name}", f"符合 {image_kind} 用途", *asset.visual_locks]
    if asset.asset_type in {"character", "prop"}:
        criteria.append("纯白或近白干净背景，没有剧情场景")
    else:
        criteria.append("空间结构清晰，没有人物和剧情事件")
    return tuple(criteria)


def _text_model_usable(config: ModelConfig | None) -> bool:
    return _model_usable(config)


def _vision_model_usable(config: ModelConfig | None) -> bool:
    return _model_usable(config)


def _model_usable(config: ModelConfig | None) -> bool:
    if config is None or not str(config.model or "").strip():
        return False
    if str(config.api_key or "").strip() or str(config.provider or "").strip().lower() == "ollama":
        return True
    base = str(config.api_base or "").strip().lower()
    return base.startswith("http://localhost") or base.startswith("http://127.0.0.1")
