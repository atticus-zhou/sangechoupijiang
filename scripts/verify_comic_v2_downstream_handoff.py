"""Verify the comic V2 package from a downstream video-production perspective."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_comic_v2_delivery import verify_delivery


DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "comic_v2_sample.json"
DEFAULT_OUTPUT = REPO_ROOT / "output" / "comic_v2_downstream_handoff"

CHARACTER_REQUIRED_IMAGES = {"three_view", "expression_sheet"}
PROP_REQUIRED_IMAGES = {"turnaround"}
SCENE_REQUIRED_IMAGES = {"wide", "top_down"}


def verify_downstream_handoff(
    fixture: Path = DEFAULT_FIXTURE,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    delivery = verify_delivery(fixture, output_dir)
    manifest_path = Path(str(delivery["handoff_manifest_path"]))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    errors: list[str] = []
    story = manifest.get("story") or {}
    style = manifest.get("style") or {}
    manifest_meta = manifest.get("manifest") or {}
    word_canvas = manifest.get("word_canvas") or {}
    assets = manifest.get("assets") or []
    shots = manifest.get("shots") or []
    images = manifest.get("images") or []

    _require_fields(errors, "story", story, ["story_id", "story_version", "title", "source_hash"])
    _require_fields(errors, "style", style, ["style_id", "style_version", "medium", "era", "aspect_ratio"])
    _require_fields(errors, "manifest", manifest_meta, ["manifest_id", "manifest_version", "manifest_hash"])
    _require_fields(errors, "word_canvas", word_canvas, ["filename", "relative_path"])

    image_ids = {item.get("image_id") for item in images if item.get("image_id")}
    asset_ids = {item.get("asset_id") for item in assets if item.get("asset_id")}
    asset_failures = _asset_handoff_failures(assets, image_ids)
    shot_failures = _shot_handoff_failures(shots, asset_ids, image_ids)
    lineage_failures = _lineage_failures(manifest.get("production_lineage") or [])
    prompt_quality_failures = _prompt_quality_failures(images, shots)

    errors.extend(asset_failures)
    errors.extend(shot_failures)
    errors.extend(lineage_failures)
    errors.extend(prompt_quality_failures)

    result = {
        "status": "passed" if not errors else "failed",
        "delivery_status": "passed" if delivery.get("handoff_ready") else "failed",
        "word_canvas": delivery.get("path"),
        "handoff_manifest": str(manifest_path),
        "story_id": story.get("story_id"),
        "story_version": story.get("story_version"),
        "style_id": style.get("style_id"),
        "style_version": style.get("style_version"),
        "asset_count": len(assets),
        "image_count": len(images),
        "shot_count": len(shots),
        "character_identity_sets": _count_assets_with_images(assets, CHARACTER_REQUIRED_IMAGES, "character"),
        "prop_reference_sets": _count_assets_with_images(assets, PROP_REQUIRED_IMAGES, "prop"),
        "scene_spatial_sets": _count_assets_with_images(assets, SCENE_REQUIRED_IMAGES, "scene"),
        "shot_video_packages": len(shots) - len(shot_failures),
        "clean_asset_prompt_sets": _count_clean_asset_prompt_sets(images),
        "director_prompt_sets": len(shots) - len(_shot_prompt_quality_failures(shots)),
        "lineage_stage_count": len(manifest.get("production_lineage") or []),
        "errors": errors,
        "downstream_handoff_ready": not errors and bool(delivery.get("handoff_ready")),
    }
    if not result["downstream_handoff_ready"]:
        result["status"] = "failed"
    return result


def _require_fields(errors: list[str], label: str, payload: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        if payload.get(field) in (None, "", []):
            errors.append(f"{label}.{field} missing")


def _asset_handoff_failures(assets: list[dict[str, Any]], image_ids: set[str]) -> list[str]:
    failures: list[str] = []
    for asset in assets:
        asset_id = asset.get("asset_id") or "<missing_asset_id>"
        image_by_kind = asset.get("image_ids_by_kind") or {}
        required = _required_images_for_asset(asset)
        if required and not required.issubset(set(image_by_kind)):
            failures.append(f"{asset_id}: missing required image kinds {sorted(required - set(image_by_kind))}")
        baseline = asset.get("identity_baseline_image_id")
        if not baseline or baseline not in image_ids:
            failures.append(f"{asset_id}: missing approved identity baseline image")
        if not asset.get("visual_locks") or not asset.get("allowed_changes") or not asset.get("story_purpose"):
            failures.append(f"{asset_id}: missing identity card fields")
    return failures


def _required_images_for_asset(asset: dict[str, Any]) -> set[str]:
    asset_type = asset.get("asset_type")
    if asset_type == "character":
        return CHARACTER_REQUIRED_IMAGES
    if asset_type == "prop":
        return PROP_REQUIRED_IMAGES
    if asset_type == "scene":
        return SCENE_REQUIRED_IMAGES
    return set()


def _shot_handoff_failures(
    shots: list[dict[str, Any]],
    asset_ids: set[str],
    image_ids: set[str],
) -> list[str]:
    failures: list[str] = []
    for shot in shots:
        shot_id = shot.get("shot_id") or "<missing_shot_id>"
        refs = shot.get("reference_asset_ids") or []
        if not refs:
            failures.append(f"{shot_id}: missing reference assets")
        missing_assets = [asset_id for asset_id in refs if asset_id not in asset_ids]
        if missing_assets:
            failures.append(f"{shot_id}: references unknown assets {missing_assets}")
        first_frame = shot.get("first_frame_reference_image") or {}
        if first_frame.get("image_id") not in image_ids:
            failures.append(f"{shot_id}: first-frame reference image is not in approved images")
        if not shot.get("video_prompt_block") or not shot.get("negative_prompt_block"):
            failures.append(f"{shot_id}: missing copyable video prompt blocks")
        if len(shot.get("execution_steps") or []) < 3:
            failures.append(f"{shot_id}: missing downstream execution steps")
        if len(shot.get("acceptance_criteria") or []) < 3:
            failures.append(f"{shot_id}: missing acceptance criteria")
        if not shot.get("retry_strategy"):
            failures.append(f"{shot_id}: missing retry strategy")
    return failures


def _lineage_failures(lineage: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    required_stages = {
        "story_contract",
        "visual_bible",
        "asset_manifest",
        "prompt_package",
        "image_production",
        "visual_review",
        "delivery",
    }
    stages = {item.get("stage") for item in lineage}
    missing = sorted(required_stages - stages)
    if missing:
        failures.append("production_lineage missing stages: " + ", ".join(missing))
    for item in lineage:
        if not item.get("department") or not item.get("agent") or not item.get("handoff_to"):
            failures.append(f"production_lineage.{item.get('stage', '<unknown>')}: missing owner or handoff")
    return failures


def _prompt_quality_failures(
    images: list[dict[str, Any]],
    shots: list[dict[str, Any]],
) -> list[str]:
    return _asset_prompt_quality_failures(images) + _shot_prompt_quality_failures(shots)


def _asset_prompt_quality_failures(images: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for image in images:
        image_id = image.get("image_id") or "<missing_image_id>"
        image_kind = image.get("image_kind") or ""
        asset_id = image.get("asset_id") or ""
        prompt = str(image.get("generator_prompt") or "")
        negative_items = image.get("negative_prompt") or []
        negative_text = "；".join(str(item) for item in negative_items)
        combined = f"{prompt}；{negative_text}"

        if "不要" in combined:
            failures.append(f"{image_id}: prompt uses unreadable negation, use 禁止 instead")
        if not prompt or not negative_items:
            failures.append(f"{image_id}: missing generator prompt or negative prompt list")
        if not all(str(item).startswith("禁止") for item in negative_items):
            failures.append(f"{image_id}: negative prompt items must start with 禁止")
        if "风格身份" not in prompt or "资产ID" not in prompt:
            failures.append(f"{image_id}: prompt missing style identity or asset id")

        if asset_id.startswith("character_"):
            if "纯白或近白色干净背景" not in prompt:
                failures.append(f"{image_id}: character asset prompt must require clean white background")
            if image_kind == "three_view" and "三视图" not in prompt:
                failures.append(f"{image_id}: character three_view prompt must explicitly request 三视图")
            if image_kind == "expression_sheet" and "表情表" not in prompt:
                failures.append(f"{image_id}: character expression_sheet prompt must explicitly request 表情表")
            if "禁止剧情动作" not in negative_text or "禁止剧情场景" not in negative_text:
                failures.append(f"{image_id}: character negative prompt must forbid story action and scenes")

        if asset_id.startswith("prop_"):
            if "纯白或近白色干净背景" not in prompt:
                failures.append(f"{image_id}: prop asset prompt must require clean white background")
            if image_kind == "turnaround" and not any(token in prompt for token in ("多角度", "转面")):
                failures.append(f"{image_id}: prop turnaround prompt must request multi-angle reference")
            if "禁止人物手持或人物入镜" not in negative_text or "禁止剧情现场" not in negative_text:
                failures.append(f"{image_id}: prop negative prompt must forbid hands/people and story scenes")

        if asset_id.startswith("scene_"):
            if image_kind == "wide" and "广角空间图" not in prompt:
                failures.append(f"{image_id}: scene wide prompt must request a wide spatial view")
            if image_kind == "top_down" and "俯视" not in prompt:
                failures.append(f"{image_id}: scene top_down prompt must request a top-down view")
            if "只展示空场景" not in prompt:
                failures.append(f"{image_id}: scene prompt must keep the asset as an empty spatial reference")
            if "禁止人物和人物互动" not in negative_text or "禁止剧情事件" not in negative_text:
                failures.append(f"{image_id}: scene negative prompt must forbid characters and story events")
    return failures


def _shot_prompt_quality_failures(shots: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    required_video_markers = ["首帧参考", "故事目的", "动作链", "表演意图", "摄影", "灯光"]
    for shot in shots:
        shot_id = shot.get("shot_id") or "<missing_shot_id>"
        video_prompt = str(shot.get("video_prompt_block") or "")
        negative_prompt = str(shot.get("negative_prompt_block") or "")
        if "不要" in f"{video_prompt}；{negative_prompt}":
            failures.append(f"{shot_id}: prompt uses unreadable negation, use 禁止 instead")
        missing = [marker for marker in required_video_markers if marker not in video_prompt]
        if missing:
            failures.append(f"{shot_id}: video prompt missing director markers {missing}")
        if not negative_prompt.startswith("禁止"):
            failures.append(f"{shot_id}: negative prompt block must be separate and start with 禁止")
        if "严格继承参考资产" not in video_prompt:
            failures.append(f"{shot_id}: video prompt must lock approved asset identity")
        if "禁止资产身份漂移" not in negative_prompt or "禁止动作顺序混乱" not in negative_prompt:
            failures.append(f"{shot_id}: negative prompt must cover identity drift and action order")
    return failures


def _count_clean_asset_prompt_sets(images: list[dict[str, Any]]) -> int:
    failures = set()
    for failure in _asset_prompt_quality_failures(images):
        failures.add(failure.split(":", 1)[0])
    return len({image.get("image_id") for image in images if image.get("image_id") and image.get("image_id") not in failures})


def _count_assets_with_images(
    assets: list[dict[str, Any]],
    required: set[str],
    asset_type: str,
) -> int:
    count = 0
    for asset in assets:
        if asset.get("asset_type") != asset_type:
            continue
        if required.issubset(set((asset.get("image_ids_by_kind") or {}).keys())):
            count += 1
    return count


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Comic V2 Downstream Handoff Audit",
        "",
        f"Status: `{result.get('status')}`",
        f"Downstream handoff ready: `{result.get('downstream_handoff_ready')}`",
        f"Word canvas: `{result.get('word_canvas')}`",
        f"Handoff manifest: `{result.get('handoff_manifest')}`",
        "",
        "## Package Shape",
        "",
        f"- Story: `{result.get('story_id')}` v{result.get('story_version')}",
        f"- Style: `{result.get('style_id')}` v{result.get('style_version')}",
        f"- Assets: {result.get('asset_count')}",
        f"- Images: {result.get('image_count')}",
        f"- Shots: {result.get('shot_count')}",
        f"- Lineage stages: {result.get('lineage_stage_count')}",
        "",
        "## Downstream Readiness",
        "",
        f"- Character identity sets: {result.get('character_identity_sets')}",
        f"- Prop reference sets: {result.get('prop_reference_sets')}",
        f"- Scene spatial sets: {result.get('scene_spatial_sets')}",
        f"- Shot video packages: {result.get('shot_video_packages')}",
        f"- Clean asset prompt sets: {result.get('clean_asset_prompt_sets')}",
        f"- Director prompt sets: {result.get('director_prompt_sets')}",
    ]
    if result.get("errors"):
        lines.extend(["", "## Issues", ""])
        lines.extend(f"- {item}" for item in result["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="text")
    args = parser.parse_args()

    result = verify_downstream_handoff(args.fixture, args.output_dir)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(format_markdown(result))
    else:
        print(f"Comic V2 downstream handoff: {result['status']}")
        if result.get("errors"):
            print("\n".join(result["errors"]))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
