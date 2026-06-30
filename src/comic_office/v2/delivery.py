"""Strict delivery gate from approved V2 records to the Word production canvas."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .asset_manifest import AssetManifest
from .contracts import ContractBundle
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
        assets.append({
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "name": asset.name,
            "manifest_version": manifest.version,
            "evidence_quote": asset.evidence.evidence_quote,
            "scene_ids": list(asset.evidence.scene_ids),
            "story_purpose": asset.story_purpose,
            "planned_images": list(asset.planned_images),
            "image_ids": [
                image_by_asset_kind[(asset.asset_id, image_kind)].image_id
                for image_kind in asset.planned_images
                if (asset.asset_id, image_kind) in image_by_asset_kind
            ],
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
            "prompt_hash": record.prompt_hash,
            "prompt_purpose": prompt.purpose if prompt else "",
            "generator_prompt": prompt.generator_prompt if prompt else "",
            "negative_prompt": list(prompt.negative_prompt) if prompt else [],
        })
    shots = []
    for shot in prompt_package.shots:
        shots.append({
            "shot_id": shot.shot_id,
            "scene_id": shot.scene_id,
            "story_beat": shot.story_beat,
            "evidence_quote": shot.evidence_quote,
            "reference_asset_ids": list(shot.reference_asset_ids),
            "action_chain": list(shot.action_chain),
            "generator_prompt": shot.generator_prompt,
            "negative_prompt": list(shot.negative_prompt),
            "retry_strategy": shot.retry_strategy,
        })
    payload = {
        "schema": "comic_production_handoff_manifest_v1",
        "story": {
            "story_id": bundle.creative.story_id,
            "story_version": bundle.creative.story_version,
            "title": bundle.creative.title,
            "source_hash": bundle.creative.source_hash,
        },
        "style": {
            "style_id": bundle.visual.style_id,
            "style_version": bundle.visual.style_version,
            "medium": bundle.visual.medium,
            "era": bundle.visual.era,
            "aspect_ratio": bundle.visual.aspect_ratio,
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
        "assets": assets,
        "images": images,
        "shots": shots,
        "audit": asdict(audit),
    }
    path = word_path.with_name(f"{word_path.stem}_handoff_manifest.json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
