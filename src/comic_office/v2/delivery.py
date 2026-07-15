"""Strict delivery gate from approved V2 records to the Word production canvas."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .asset_manifest import AssetManifest
from .contracts import ContractBundle
from .production_benchmark import audit_handoff_manifest
from .production import ImageProductionResult, PromptPackage
from .word_canvas import CanvasBuildResult, build_word_canvas_v2


class DeliveryValidationError(RuntimeError):
    """Raised when a V2 package is incomplete, stale, or not approved."""


def build_delivery_from_v2(
    bundle: ContractBundle,
    manifest: AssetManifest,
    prompt_package: PromptPackage,
    image_result: ImageProductionResult,
    output_dir: Path,
    *,
    allow_human_override: bool = False,
) -> CanvasBuildResult:
    """Validate every reference before producing a strict page-based DOCX."""
    _validate_bindings(bundle, manifest, prompt_package)
    expected = {(item.asset_id, kind) for item in manifest.items for kind in item.planned_images}
    prompts = {(item.object_id, item.image_kind): item for item in prompt_package.prompts}
    if set(prompts) != expected:
        missing = sorted(expected - set(prompts))
        raise DeliveryValidationError(f"提示词包缺少计划图片：{missing}")
    records = {(item.asset_id, item.image_kind): item for item in image_result.records}
    missing_records = sorted(expected - set(records))
    if missing_records:
        raise DeliveryValidationError(f"缺少已批准图片：{missing_records}")
    image_paths: dict[str, dict[str, str]] = {}
    for key in sorted(expected):
        record = records[key]
        if record.status != "approved" and not allow_human_override:
            raise DeliveryValidationError(f"图片尚未批准：{record.image_id}")
        if (
            record.story_id != bundle.creative.story_id
            or record.story_version != bundle.creative.story_version
            or record.style_id != bundle.visual.style_id
            or record.style_version != bundle.visual.style_version
            or record.manifest_version != manifest.version
        ):
            raise DeliveryValidationError(f"图片版本与当前合同不一致：{record.image_id}")
        if not Path(record.path).exists():
            raise DeliveryValidationError(f"图片文件不存在：{record.image_id}")
        image_paths.setdefault(record.asset_id, {})[record.image_kind] = record.path
    asset_ids = {item.asset_id for item in manifest.items}
    if not prompt_package.shots:
        raise DeliveryValidationError("镜头提示词卡为空")
    for shot in prompt_package.shots:
        missing_refs = set(shot.reference_asset_ids) - asset_ids
        if missing_refs:
            raise DeliveryValidationError(f"{shot.shot_id} 引用了不存在的资产：{sorted(missing_refs)}")
        if not shot.evidence_quote or shot.evidence_quote not in bundle.creative.source_story:
            raise DeliveryValidationError(f"{shot.shot_id} 缺少确认故事证据")
        if not shot.generator_prompt.strip():
            raise DeliveryValidationError(f"{shot.shot_id} 缺少视频生成提示词")
        if not shot.acceptance_criteria:
            raise DeliveryValidationError(f"{shot.shot_id} 缺少镜头验收标准")
        if not shot.platform_note.strip():
            raise DeliveryValidationError(f"{shot.shot_id} 缺少平台执行备注")
    result = build_word_canvas_v2(
        bundle,
        manifest,
        prompt_package.shots,
        image_paths,
        Path(output_dir),
        asset_prompts=prompts,
        require_all_planned_images=True,
    )
    if not result.audit.handoff_ready:
        raise DeliveryValidationError(
            f"Word 结构审计未通过：缺图={result.audit.missing_image_asset_ids}，"
            f"结构错误={result.audit.structural_errors}"
        )
    handoff_manifest_path = _write_handoff_manifest(
        result.path,
        bundle,
        manifest,
        prompt_package,
        image_result,
        result.audit,
    )
    return CanvasBuildResult(
        path=result.path,
        audit=result.audit,
        handoff_manifest_path=handoff_manifest_path,
    )


def _validate_bindings(
    bundle: ContractBundle,
    manifest: AssetManifest,
    prompt_package: PromptPackage,
) -> None:
    if manifest.story_id != bundle.creative.story_id or manifest.story_version != bundle.creative.story_version:
        raise DeliveryValidationError("资产清单属于另一版故事")
    if manifest.style_id != bundle.visual.style_id or manifest.style_version != bundle.visual.style_version:
        raise DeliveryValidationError("资产清单属于另一版视觉母版")
    if prompt_package.story_id != bundle.creative.story_id or prompt_package.story_version != bundle.creative.story_version:
        raise DeliveryValidationError("提示词包属于另一版故事")
    if prompt_package.style_id != bundle.visual.style_id or prompt_package.style_version != bundle.visual.style_version:
        raise DeliveryValidationError("提示词包属于另一版视觉母版")
    if prompt_package.manifest_id != manifest.manifest_id or prompt_package.manifest_version != manifest.version:
        raise DeliveryValidationError("提示词包属于另一版资产清单")


def _write_handoff_manifest(
    word_path: Path,
    bundle: ContractBundle,
    manifest: AssetManifest,
    prompt_package: PromptPackage,
    image_result: ImageProductionResult,
    audit,
) -> Path:
    """Write a sidecar manifest that keeps the asset/image/shot chain inspectable."""
    prompt_by_asset_kind = {
        (prompt.object_id, prompt.image_kind): prompt
        for prompt in prompt_package.prompts
    }
    image_by_asset_kind = {
        (record.asset_id, record.image_kind): record
        for record in image_result.records
    }
    assets = []
    for asset in manifest.items:
        asset_images = [
            image_by_asset_kind[(asset.asset_id, image_kind)]
            for image_kind in asset.planned_images
            if (asset.asset_id, image_kind) in image_by_asset_kind
        ]
        identity_baseline = next((record for record in asset_images if record.is_identity_baseline), asset_images[0] if asset_images else None)
        assets.append({
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "type_label": {
                "character": "人物",
                "prop": "道具",
                "scene": "场景",
            }.get(asset.asset_type, asset.asset_type),
            "name": asset.name,
            "manifest_version": manifest.version,
            "evidence_quote": asset.evidence.evidence_quote,
            "scene_ids": list(asset.evidence.scene_ids),
            "story_purpose": asset.story_purpose,
            "visual_locks": list(asset.visual_locks),
            "allowed_changes": list(asset.allowed_changes),
            "planned_images": list(asset.planned_images),
            "review_status": asset.review_status,
            "identity_baseline_image_id": identity_baseline.image_id if identity_baseline else "",
            "identity_baseline_image_kind": identity_baseline.image_kind if identity_baseline else "",
            "image_ids": [record.image_id for record in asset_images],
            "image_ids_by_kind": {
                record.image_kind: record.image_id
                for record in asset_images
            },
        })
    images = []
    for record in image_result.records:
        prompt = prompt_by_asset_kind.get((record.asset_id, record.image_kind))
        images.append({
            "image_id": record.image_id,
            "asset_id": record.asset_id,
            "image_kind": record.image_kind,
            "file": Path(record.path).name,
            "provider": record.provider,
            "model": record.model,
            "status": record.status,
            "is_identity_baseline": record.is_identity_baseline,
            "reference_image_ids": list(record.reference_image_ids),
            "story_id": record.story_id,
            "story_version": record.story_version,
            "style_id": record.style_id,
            "style_version": record.style_version,
            "manifest_version": record.manifest_version,
            "prompt_hash": record.prompt_hash,
            "prompt_purpose": prompt.purpose if prompt else "",
            "production_role": prompt.production_role if prompt else "",
            "clean_background_required": bool(prompt.clean_background_required) if prompt else False,
            "generator_prompt": prompt.generator_prompt if prompt else "",
            "negative_prompt": list(prompt.negative_prompt) if prompt else [],
            "review": dict(record.review or {}),
        })
    shots = []
    for shot in prompt_package.shots:
        reference_images = _shot_reference_images(shot.reference_asset_ids, image_result.records)
        reference_asset_chain = _shot_reference_asset_chain(shot.reference_asset_ids, manifest, reference_images)
        first_frame_reference = reference_images[0] if reference_images else {}
        shots.append({
            "shot_id": shot.shot_id,
            "scene_id": shot.scene_id,
            "story_beat": shot.story_beat,
            "evidence_quote": shot.evidence_quote,
            "style_id": shot.style_id,
            "style_version": bundle.visual.style_version,
            "reference_asset_ids": list(shot.reference_asset_ids),
            "reference_images": reference_images,
            "first_frame_reference_image": first_frame_reference,
            "reference_asset_chain": reference_asset_chain,
            "action_chain": list(shot.action_chain),
            "director_execution": {
                "contract_version": 1,
                "style_id": shot.style_id,
                "style_version": bundle.visual.style_version,
                "first_frame_image_id": first_frame_reference.get("image_id", ""),
                "reference_asset_ids": list(shot.reference_asset_ids),
                "action_chain": list(shot.action_chain),
                "performance_intent": shot.performance_intent,
                "framing": shot.framing,
                "camera_movement": shot.camera_movement,
                "lighting": shot.lighting,
                "dialogue": shot.dialogue,
                "sound": shot.sound,
            },
            "generator_prompt": shot.generator_prompt,
            "negative_prompt": list(shot.negative_prompt),
            "video_prompt_block": shot.generator_prompt,
            "negative_prompt_block": "；".join(shot.negative_prompt),
            "execution_steps": [
                "绑定首帧参考图片：" + (reference_images[0]["file"] if reference_images else "未绑定图片"),
                "粘贴视频提示词，并保持动作链顺序：" + " -> ".join(shot.action_chain),
                "按验收标准检查人物、道具、场景、运镜和故事节点。",
                "失败时执行重试策略：" + shot.retry_strategy,
            ],
            "retry_strategy": shot.retry_strategy,
            "acceptance_criteria": list(shot.acceptance_criteria),
            "platform_note": shot.platform_note,
        })
    payload = {
        "schema": "comic_production_handoff_manifest_v3",
        "schema_version": 3,
        "story": {
            "story_id": bundle.creative.story_id,
            "story_version": bundle.creative.story_version,
            "title": bundle.creative.title,
            "source_hash": bundle.creative.source_hash,
            "source_mode": bundle.creative.source_mode,
            "source_story": bundle.creative.source_story,
            "genre": bundle.creative.genre,
            "theme": bundle.creative.theme,
            "protagonist_goal": bundle.creative.protagonist_goal,
            "main_conflict": bundle.creative.main_conflict,
            "causal_chain": list(bundle.creative.causal_chain),
            "ending": bundle.creative.ending,
            "episodes": [asdict(item) for item in bundle.creative.episodes],
            "must_keep": list(bundle.creative.must_keep),
            "must_avoid": list(bundle.creative.must_avoid),
        },
        "style": {
            "style_id": bundle.visual.style_id,
            "style_version": bundle.visual.style_version,
            "medium": bundle.visual.medium,
            "era": bundle.visual.era,
            "aspect_ratio": bundle.visual.aspect_ratio,
            "palette": list(bundle.visual.palette),
            "lighting": bundle.visual.lighting,
            "camera_language": bundle.visual.camera_language,
            "character_rules": list(bundle.visual.character_rules),
            "costume_rules": list(bundle.visual.costume_rules),
            "prop_rules": list(bundle.visual.prop_rules),
            "architecture_rules": list(bundle.visual.architecture_rules),
            "visual_motifs": list(bundle.visual.visual_motifs),
            "prohibited_elements": list(bundle.visual.prohibited_elements),
        },
        "manifest": {
            "manifest_id": manifest.manifest_id,
            "manifest_version": manifest.version,
            "manifest_hash": manifest.manifest_hash,
        },
        "prompt_package": {
            "package_id": prompt_package.package_id,
            "prompt_count": len(prompt_package.prompts),
            "shot_count": len(prompt_package.shots),
        },
        "word_canvas": {
            "filename": word_path.name,
            "relative_path": word_path.name,
        },
        "production_lineage": _production_lineage(
            bundle,
            manifest,
            prompt_package,
            image_result,
            audit,
        ),
        "assets": assets,
        "images": images,
        "shots": shots,
        "audit": asdict(audit),
    }
    payload["quality_benchmark"] = audit_handoff_manifest(payload)
    path = word_path.with_name(f"{word_path.stem}_handoff_manifest.json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _production_lineage(
    bundle: ContractBundle,
    manifest: AssetManifest,
    prompt_package: PromptPackage,
    image_result: ImageProductionResult,
    audit,
) -> list[dict[str, str]]:
    """Describe which office agents owned each handoff-critical production step."""
    return [
        {
            "stage": "story_contract",
            "stage_label": "故事合同",
            "department": "内阁 / 中书省",
            "agent": "主创对话官 / 中书省",
            "status": "confirmed",
            "human_checkpoint": "用户确认故事后，后续部门只能按这版故事拆解，不得擅自改写。",
            "handoff_to": "视觉母版",
            "acceptance_criteria": "故事原文、故事版本和禁止改写规则齐全。",
            "output": f"{bundle.creative.title} v{bundle.creative.story_version}",
        },
        {
            "stage": "visual_bible",
            "stage_label": "风格圣经",
            "department": "中书省 / 门下省",
            "agent": "美术设定官 / 连续性审核官",
            "status": "locked",
            "human_checkpoint": "用户确认画风方向后，人物、道具、场景和镜头提示词都必须引用同一套视觉规则。",
            "handoff_to": "资产拆解",
            "acceptance_criteria": "视觉母版包含画风、时代、比例、色彩、服装和禁用元素。",
            "output": f"{bundle.visual.medium} · {bundle.visual.aspect_ratio}",
        },
        {
            "stage": "asset_manifest",
            "stage_label": "资产拆解",
            "department": "中书省 / 门下省",
            "agent": "资产拆解官 / 设定审校官",
            "status": manifest.review_status,
            "human_checkpoint": "人物、道具、场景拆解需要用户审核；退回意见必须进入下一版拆解。",
            "handoff_to": "提示词与镜头执行包",
            "acceptance_criteria": "每个资产都有原文证据、故事用途、计划图片和审核状态。",
            "output": f"{len(manifest.items)} assets · manifest v{manifest.version}",
        },
        {
            "stage": "prompt_package",
            "stage_label": "提示词与镜头执行包",
            "department": "兵部 / 刑部",
            "agent": "镜头调度官 / 提示词质检官",
            "status": "ready",
            "human_checkpoint": "用户确认资产拆解后，兵部才能生成镜头、动作链和可执行提示词。",
            "handoff_to": "基础图片生产",
            "acceptance_criteria": "资产提示词和镜头卡引用已审核资产，并把负面提示词单独列出。",
            "output": f"{len(prompt_package.prompts)} asset prompts · {len(prompt_package.shots)} shot cards",
        },
        {
            "stage": "image_production",
            "stage_label": "基础图片生产",
            "department": "工部",
            "agent": "图片生成官",
            "status": image_result.status,
            "human_checkpoint": "失败、低分或风格不一致的图片需要重新生成或人工放行。",
            "handoff_to": "一致性质检",
            "acceptance_criteria": "人物和道具基础图保持干净白底，场景图保留空间信息。",
            "output": f"{len(image_result.records)} image records",
        },
        {
            "stage": "visual_review",
            "stage_label": "一致性质检",
            "department": "刑部",
            "agent": "一致性审核官",
            "status": "passed" if image_result.production_ready else "needs_review",
            "human_checkpoint": "交付前必须检查人物脸型、服装、道具、场景风格和引用关系。",
            "handoff_to": "Word 画布交付",
            "acceptance_criteria": "图片通过身份、风格、时代、空间和用途检查，风险项有处理结论。",
            "output": f"{len(image_result.failures)} failures",
        },
        {
            "stage": "delivery",
            "stage_label": "Word 画布交付",
            "department": "礼部 / 刑部",
            "agent": "交付排版官 / 结构审计官",
            "status": "handoff_ready" if audit.handoff_ready else "needs_review",
            "human_checkpoint": "最终 Word 画布和引用清单必须一起交付，方便外部视频平台按图引用。",
            "handoff_to": "下游视频平台",
            "acceptance_criteria": "Word 画布、图片、镜头卡和 handoff manifest 可下载且引用一致。",
            "output": f"{audit.embedded_images} embedded images",
        },
    ]


def _shot_reference_images(asset_ids: tuple[str, ...], records: tuple) -> list[dict[str, str]]:
    references = []
    for asset_id in asset_ids:
        candidates = [record for record in records if record.asset_id == asset_id]
        if not candidates:
            continue
        record = next((item for item in candidates if item.is_identity_baseline), candidates[0])
        references.append({
            "asset_id": record.asset_id,
            "image_id": record.image_id,
            "image_kind": record.image_kind,
            "file": Path(record.path).name,
        })
    return references


def _shot_reference_asset_chain(
    asset_ids: tuple[str, ...],
    manifest: AssetManifest,
    reference_images: list[dict[str, str]],
) -> list[dict[str, str]]:
    asset_by_id = {asset.asset_id: asset for asset in manifest.items}
    image_by_asset_id = {image["asset_id"]: image for image in reference_images}
    chain = []
    for asset_id in asset_ids:
        asset = asset_by_id.get(asset_id)
        image = image_by_asset_id.get(asset_id, {})
        chain.append({
            "asset_id": asset_id,
            "name": asset.name if asset else "",
            "asset_type": asset.asset_type if asset else "",
            "story_purpose": asset.story_purpose if asset else "",
            "first_frame_image_id": image.get("image_id", ""),
            "first_frame_image_kind": image.get("image_kind", ""),
            "first_frame_file": image.get("file", ""),
        })
    return chain
