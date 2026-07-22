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
from src.comic_office.v2.prompt_quality import audit_prompt_package


DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "comic_v2_sample.json"
DEFAULT_OUTPUT = REPO_ROOT / "output" / "comic_v2_downstream_handoff"

CHARACTER_REQUIRED_IMAGES = {"three_view", "expression_sheet"}
PROP_REQUIRED_IMAGES = {"turnaround"}
SCENE_REQUIRED_IMAGES = {"wide", "top_down"}
DIRECTOR_EXECUTION_REQUIRED_FIELDS = {
    "contract_version",
    "style_id",
    "style_version",
    "story_purpose",
    "first_frame_image_id",
    "reference_asset_ids",
    "action_chain",
    "performance_intent",
    "framing",
    "camera_movement",
    "lighting",
    "dialogue",
    "sound",
}


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
    quick_start_failures = _quick_start_failures(manifest.get("downstream_quick_start") or [], shots)
    prompt_quality = _prompt_quality_audit(images, shots)
    image_contracts = _image_contract_counts(images)
    shot_references = _shot_reference_counts(shots, asset_ids, image_ids)
    prompt_quality_failures = [
        f"{item.get('id', '<unknown>')}: {item.get('message', '')}"
        for item in prompt_quality.get("issues", [])
    ]

    errors.extend(asset_failures)
    errors.extend(shot_failures)
    errors.extend(lineage_failures)
    errors.extend(quick_start_failures)
    errors.extend(prompt_quality_failures)

    result = {
        "status": "passed" if not errors else "failed",
        "delivery_status": "passed" if delivery.get("handoff_ready") else "failed",
        "word_canvas": delivery.get("path"),
        "handoff_manifest": str(manifest_path),
        "output_dir": delivery.get("output_dir") or str(output_dir),
        "word_canvas_exists": delivery.get("word_canvas_exists"),
        "word_canvas_bytes": delivery.get("word_canvas_bytes", 0),
        "handoff_manifest_exists": manifest_path.is_file(),
        "handoff_manifest_bytes": manifest_path.stat().st_size if manifest_path.is_file() else 0,
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
        "shot_video_packages": _count_ready_shots(shots, asset_ids, image_ids),
        "structured_director_shots": _count_structured_director_shots(shots),
        "clean_asset_prompt_sets": prompt_quality.get("clean_asset_prompt_count", 0),
        "director_prompt_sets": prompt_quality.get("director_prompt_count", 0),
        "image_usage_contracts": image_contracts["usage_contracts"],
        "image_reference_policies": image_contracts["reference_policies"],
        "clean_background_asset_images": image_contracts["clean_background_asset_images"],
        "first_frame_bound_shots": shot_references["first_frame_bound_shots"],
        "complete_reference_chain_shots": shot_references["complete_reference_chain_shots"],
        "reference_asset_links": shot_references["reference_asset_links"],
        "lineage_stage_count": len(manifest.get("production_lineage") or []),
        "quick_start_step_count": len(manifest.get("downstream_quick_start") or []),
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
        failures.extend(_first_frame_reference_failures(shot, asset_ids, image_ids))
        failures.extend(_reference_asset_chain_failures(shot, asset_ids, image_ids))
        failures.extend(_shot_story_purpose_failures(shot))
        if not shot.get("video_prompt_block") or not shot.get("negative_prompt_block"):
            failures.append(f"{shot_id}: missing copyable video prompt blocks")
        if len(shot.get("execution_steps") or []) < 3:
            failures.append(f"{shot_id}: missing downstream execution steps")
        if len(shot.get("acceptance_criteria") or []) < 3:
            failures.append(f"{shot_id}: missing acceptance criteria")
        if not shot.get("retry_strategy"):
            failures.append(f"{shot_id}: missing retry strategy")
        failures.extend(_director_execution_failures(shot))
    return failures


def _shot_story_purpose_failures(shot: dict[str, Any]) -> list[str]:
    shot_id = shot.get("shot_id") or "<missing_shot_id>"
    story_purpose = str(shot.get("story_purpose") or "").strip()
    video_prompt = str(shot.get("video_prompt_block") or "")
    failures: list[str] = []
    if not story_purpose:
        failures.append(f"{shot_id}: missing shot story_purpose")
        return failures
    if story_purpose not in video_prompt:
        failures.append(f"{shot_id}: video prompt does not include shot story_purpose")
    return failures


def _first_frame_reference_failures(
    shot: dict[str, Any],
    asset_ids: set[str],
    image_ids: set[str],
) -> list[str]:
    shot_id = shot.get("shot_id") or "<missing_shot_id>"
    first_frame = shot.get("first_frame_reference_image") or {}
    failures = []
    required_fields = ("image_id", "asset_id", "file", "image_kind")
    missing = [field for field in required_fields if not str(first_frame.get(field) or "").strip()]
    if missing:
        failures.append(f"{shot_id}: first-frame reference image missing fields {missing}")
        return failures
    if first_frame.get("image_id") not in image_ids:
        failures.append(f"{shot_id}: first-frame reference image_id is not approved")
    if first_frame.get("asset_id") not in asset_ids:
        failures.append(f"{shot_id}: first-frame reference asset_id is not approved")
    if first_frame.get("asset_id") not in set(shot.get("reference_asset_ids") or []):
        failures.append(f"{shot_id}: first-frame asset is not part of shot reference assets")
    if not str(first_frame.get("file") or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        failures.append(f"{shot_id}: first-frame reference file must be an image file")
    return failures


def _reference_asset_chain_failures(
    shot: dict[str, Any],
    asset_ids: set[str],
    image_ids: set[str],
) -> list[str]:
    shot_id = shot.get("shot_id") or "<missing_shot_id>"
    refs = list(shot.get("reference_asset_ids") or [])
    chain = list(shot.get("reference_asset_chain") or [])
    failures = []
    if not chain:
        return [f"{shot_id}: missing machine-readable reference_asset_chain"]
    chain_ids = [item.get("asset_id") for item in chain if item.get("asset_id")]
    missing_from_chain = [asset_id for asset_id in refs if asset_id not in chain_ids]
    if missing_from_chain:
        failures.append(f"{shot_id}: reference_asset_chain missing assets {missing_from_chain}")
    unknown_chain_assets = [asset_id for asset_id in chain_ids if asset_id not in asset_ids]
    if unknown_chain_assets:
        failures.append(f"{shot_id}: reference_asset_chain includes unknown assets {unknown_chain_assets}")
    for index, item in enumerate(chain, start=1):
        label = f"{shot_id}: reference_asset_chain[{index}]"
        required_fields = ("asset_id", "asset_type", "name", "first_frame_image_id", "first_frame_file")
        missing = [field for field in required_fields if not str(item.get(field) or "").strip()]
        if missing:
            failures.append(f"{label} missing fields {missing}")
            continue
        if item.get("first_frame_image_id") not in image_ids:
            failures.append(f"{label} first_frame_image_id is not approved")
        if not str(item.get("first_frame_file") or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            failures.append(f"{label} first_frame_file must be an image file")
    return failures


def _director_execution_failures(shot: dict[str, Any]) -> list[str]:
    shot_id = shot.get("shot_id") or "<missing_shot_id>"
    director = shot.get("director_execution") or {}
    missing = sorted(
        field
        for field in DIRECTOR_EXECUTION_REQUIRED_FIELDS
        if director.get(field) in (None, "", [])
    )
    failures = []
    if missing:
        failures.append(f"{shot_id}: structured director execution missing fields {missing}")
        return failures
    if director.get("contract_version") != 1:
        failures.append(f"{shot_id}: unsupported director execution contract version")
    if director.get("reference_asset_ids") != shot.get("reference_asset_ids"):
        failures.append(f"{shot_id}: director execution reference assets do not match shot references")
    if director.get("action_chain") != shot.get("action_chain"):
        failures.append(f"{shot_id}: director execution action chain does not match shot action chain")
    if director.get("story_purpose") != shot.get("story_purpose"):
        failures.append(f"{shot_id}: director execution story_purpose does not match shot story_purpose")
    if len(director.get("action_chain") or []) < 2:
        failures.append(f"{shot_id}: director execution action chain needs at least two ordered steps")
    first_frame = shot.get("first_frame_reference_image") or {}
    if director.get("first_frame_image_id") != first_frame.get("image_id"):
        failures.append(f"{shot_id}: director execution first-frame identity does not match approved image")
    return failures


def _count_ready_shots(
    shots: list[dict[str, Any]],
    asset_ids: set[str],
    image_ids: set[str],
) -> int:
    return sum(
        1
        for shot in shots
        if not _shot_handoff_failures([shot], asset_ids, image_ids)
    )


def _count_structured_director_shots(shots: list[dict[str, Any]]) -> int:
    return sum(1 for shot in shots if not _director_execution_failures(shot))


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


def _quick_start_failures(steps: list[dict[str, Any]], shots: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    if len(steps) < 5:
        failures.append("downstream_quick_start needs at least five ordered steps")
        return failures
    expected_order = list(range(1, len(steps) + 1))
    actual_order = [step.get("step") for step in steps]
    if actual_order != expected_order:
        failures.append(f"downstream_quick_start has non-sequential steps: {actual_order}")
    for step in steps:
        label = f"downstream_quick_start.{step.get('step', '<unknown>')}"
        for field in ("title", "owner", "action", "output", "acceptance"):
            if not str(step.get(field) or "").strip():
                failures.append(f"{label}: missing {field}")
        if not step.get("input_refs"):
            failures.append(f"{label}: missing input_refs")
    shot_ids = {shot.get("shot_id") for shot in shots if shot.get("shot_id")}
    shot_step = next((step for step in steps if "镜头" in str(step.get("title") or "")), {})
    if not shot_ids.issubset(set(shot_step.get("input_refs") or [])):
        failures.append("downstream_quick_start video step must reference every shot id")
    return failures


def _prompt_quality_audit(
    images: list[dict[str, Any]],
    shots: list[dict[str, Any]],
) -> dict[str, Any]:
    return audit_prompt_package({
        "prompts": [
            {
                "object_id": image.get("asset_id", ""),
                "image_kind": image.get("image_kind", ""),
                "production_role": image.get("production_role", ""),
                "clean_background_required": image.get("clean_background_required"),
                "usage_contract": image.get("usage_contract") or [],
                "reference_policy": image.get("reference_policy", ""),
                "generator_prompt": image.get("generator_prompt", ""),
                "negative_prompt": image.get("negative_prompt") or [],
            }
            for image in images
        ],
        "shots": [
            {
                "shot_id": shot.get("shot_id", ""),
                "generator_prompt": shot.get("video_prompt_block", ""),
                "negative_prompt": _split_negative_block(shot.get("negative_prompt_block", "")),
                "first_frame_reference_image": shot.get("first_frame_reference_image") or {},
                "reference_asset_chain": shot.get("reference_asset_chain") or [],
            }
            for shot in shots
        ],
    })


def _split_negative_block(text: str) -> list[str]:
    return [item.strip() for item in str(text or "").split("；") if item.strip()]


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


def _image_contract_counts(images: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "usage_contracts": sum(1 for image in images if image.get("usage_contract")),
        "reference_policies": sum(1 for image in images if str(image.get("reference_policy") or "").strip()),
        "clean_background_asset_images": sum(
            1
            for image in images
            if image.get("clean_background_required") is True
            and str(image.get("production_role") or "").startswith(("clean_character_", "clean_prop_"))
        ),
    }


def _shot_reference_counts(
    shots: list[dict[str, Any]],
    asset_ids: set[str],
    image_ids: set[str],
) -> dict[str, int]:
    first_frame_bound_shots = 0
    complete_reference_chain_shots = 0
    reference_asset_links = 0
    for shot in shots:
        first_frame = shot.get("first_frame_reference_image") or {}
        if (
            first_frame.get("image_id") in image_ids
            and first_frame.get("asset_id") in asset_ids
            and str(first_frame.get("file") or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ):
            first_frame_bound_shots += 1
        chain = list(shot.get("reference_asset_chain") or [])
        valid_links = [
            item
            for item in chain
            if item.get("asset_id") in asset_ids
            and item.get("first_frame_image_id") in image_ids
            and str(item.get("name") or "").strip()
        ]
        reference_asset_links += len(valid_links)
        refs = set(shot.get("reference_asset_ids") or [])
        if refs and refs.issubset({item.get("asset_id") for item in valid_links}):
            complete_reference_chain_shots += 1
    return {
        "first_frame_bound_shots": first_frame_bound_shots,
        "complete_reference_chain_shots": complete_reference_chain_shots,
        "reference_asset_links": reference_asset_links,
    }


def format_markdown(result: dict[str, Any]) -> str:
    word_canvas_status = _file_status(result.get("word_canvas_exists"), result.get("word_canvas_bytes"))
    manifest_status = _file_status(result.get("handoff_manifest_exists"), result.get("handoff_manifest_bytes"))
    lines = [
        "# Comic V2 Downstream Handoff Audit",
        "",
        f"Status: `{result.get('status')}`",
        f"Downstream handoff ready: `{result.get('downstream_handoff_ready')}`",
        f"Output directory: `{_display_path(result.get('output_dir'))}`",
        f"Word canvas: {word_canvas_status}",
        f"Handoff manifest: {manifest_status}",
        "",
        "## Package Shape",
        "",
        f"- Story: `{result.get('story_id')}` v{result.get('story_version')}",
        f"- Style: `{result.get('style_id')}` v{result.get('style_version')}",
        f"- Assets: {result.get('asset_count')}",
        f"- Images: {result.get('image_count')}",
        f"- Shots: {result.get('shot_count')}",
        f"- Lineage stages: {result.get('lineage_stage_count')}",
        f"- Downstream quick-start steps: {result.get('quick_start_step_count')}",
        "",
        "## Downstream Readiness",
        "",
        f"- Character identity sets: {result.get('character_identity_sets')}",
        f"- Prop reference sets: {result.get('prop_reference_sets')}",
        f"- Scene spatial sets: {result.get('scene_spatial_sets')}",
        f"- Shot video packages: {result.get('shot_video_packages')}",
        f"- Structured director shots: {result.get('structured_director_shots')}",
        f"- Quick-start playbook: {result.get('quick_start_step_count')} steps",
        f"- Clean asset prompt sets: {result.get('clean_asset_prompt_sets')}",
        f"- Director prompt sets: {result.get('director_prompt_sets')}",
        f"- Image usage contracts: {result.get('image_usage_contracts')}/{result.get('image_count')}",
        f"- Image reference policies: {result.get('image_reference_policies')}/{result.get('image_count')}",
        f"- Clean-background base asset images: {result.get('clean_background_asset_images')}",
        f"- First-frame bound shots: {result.get('first_frame_bound_shots')}/{result.get('shot_count')}",
        f"- Complete reference-chain shots: {result.get('complete_reference_chain_shots')}/{result.get('shot_count')}",
        f"- Machine-readable reference asset links: {result.get('reference_asset_links')}",
    ]
    if result.get("errors"):
        lines.extend(["", "## Issues", ""])
        lines.extend(f"- {item}" for item in result["errors"])
    return "\n".join(lines) + "\n"


def _display_path(value: object) -> str:
    if not value:
        return ""
    path = Path(str(value))
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name or str(value)


def _file_status(exists: object, size: object) -> str:
    if not exists:
        return "`missing`"
    return f"`present` ({int(size or 0)} bytes)"


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
