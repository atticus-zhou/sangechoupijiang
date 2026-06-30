"""Build and verify the deterministic comic-production V2 sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.comic_office.v2.asset_manifest import build_asset_manifest
from src.comic_office.v2.contracts import build_contract_bundle
from src.comic_office.v2.delivery import build_delivery_from_v2
from src.comic_office.v2.production import ImageProductionResult, ImageRecord, PromptPackage
from src.comic_office.v2.prompt_director import build_asset_prompt_plan, build_shot_card


def verify_delivery(fixture_path: Path, output_dir: Path) -> dict:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    bundle = build_contract_bundle(fixture["source_story"], fixture["planner_payload"])
    manifest = build_asset_manifest(bundle, fixture["assets"])
    assets_by_name = {item.name: item for item in manifest.items}
    shots = []
    for payload in fixture["shots"]:
        shots.append(build_shot_card(
            payload,
            characters=[assets_by_name[name] for name in payload["characters"]],
            props=[assets_by_name[name] for name in payload["props"]],
            scene=assets_by_name[payload["scene"]],
            visual=bundle.visual,
        ))

    image_dir = output_dir / "fixture-images"
    image_dir.mkdir(parents=True, exist_ok=True)
    prompts = []
    records = []
    for asset in manifest.items:
        for index, image_kind in enumerate(asset.planned_images):
            prompt = build_asset_prompt_plan(asset, bundle.visual, image_kind=image_kind)
            prompts.append(prompt)
            image_path = image_dir / f"{asset.asset_id}_{image_kind}.png"
            _write_placeholder_image(image_path, asset.name, image_kind, asset.asset_type)
            records.append(ImageRecord(
                image_id=f"img_{asset.asset_id}_{image_kind}",
                asset_id=asset.asset_id,
                image_kind=image_kind,
                prompt_hash=hashlib.sha256(prompt.render().encode("utf-8")).hexdigest(),
                path=str(image_path),
                provider="fixture",
                model="deterministic-placeholder",
                attempts=1,
                status="approved",
                is_identity_baseline=index == 0,
                reference_image_ids=() if index == 0 else (f"img_{asset.asset_id}_{asset.planned_images[0]}",),
                story_id=bundle.creative.story_id,
                story_version=bundle.creative.story_version,
                style_id=bundle.visual.style_id,
                style_version=bundle.visual.style_version,
                manifest_version=manifest.version,
                review={"status": "pass", "fixture": True},
            ))
    prompt_package = PromptPackage(
        package_id="prompts_fixture",
        story_id=bundle.creative.story_id,
        story_version=bundle.creative.story_version,
        style_id=bundle.visual.style_id,
        style_version=bundle.visual.style_version,
        manifest_id=manifest.manifest_id,
        manifest_version=manifest.version,
        prompts=tuple(prompts),
        shots=tuple(shots),
    )
    image_result = ImageProductionResult(
        status="ready_for_delivery",
        production_ready=True,
        records=tuple(records),
        failures=(),
    )
    build = build_delivery_from_v2(bundle, manifest, prompt_package, image_result, output_dir)
    doc = Document(build.path)
    text = "\n".join(
        [paragraph.text for paragraph in doc.paragraphs]
        + [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    )
    missing_ids = [
        identifier
        for identifier in [*(item.asset_id for item in manifest.items), *(shot.shot_id for shot in shots)]
        if identifier not in text
    ]
    if missing_ids:
        raise AssertionError(f"delivery is missing IDs: {', '.join(missing_ids)}")
    handoff_manifest_path = build.handoff_manifest_path
    if handoff_manifest_path is None or not handoff_manifest_path.exists():
        raise AssertionError("delivery handoff manifest was not created")
    handoff_manifest = json.loads(handoff_manifest_path.read_text(encoding="utf-8"))
    if handoff_manifest.get("word_canvas", {}).get("filename") != build.path.name:
        raise AssertionError("handoff manifest does not point at the generated Word canvas")
    image_prompt_ready = all(
        bool(image.get("generator_prompt")) and isinstance(image.get("negative_prompt"), list)
        for image in (handoff_manifest.get("images") or [])
    )
    if not image_prompt_ready:
        raise AssertionError("handoff manifest image records are missing executable prompts")
    asset_identity_ready = all(
        asset.get("type_label")
        and isinstance(asset.get("visual_locks"), list)
        and isinstance(asset.get("allowed_changes"), list)
        and bool(asset.get("review_status"))
        for asset in (handoff_manifest.get("assets") or [])
    )
    if not asset_identity_ready:
        raise AssertionError("handoff manifest asset records are missing identity fields")
    shot_reference_images_ready = all(
        isinstance(shot.get("reference_images"), list)
        and shot.get("reference_images")
        and all(item.get("asset_id") and item.get("image_id") and item.get("file") for item in shot.get("reference_images"))
        for shot in (handoff_manifest.get("shots") or [])
    )
    if not shot_reference_images_ready:
        raise AssertionError("handoff manifest shot records are missing reference images")
    lineage = handoff_manifest.get("production_lineage") or []
    lineage_ready = (
        isinstance(lineage, list)
        and len(lineage) >= 6
        and all(
            item.get("stage")
            and item.get("department")
            and item.get("agent")
            and item.get("status")
            and item.get("human_checkpoint")
            for item in lineage
        )
    )
    if not lineage_ready:
        raise AssertionError("handoff manifest is missing production lineage")
    audit = build.audit
    result = {
        "path": str(build.path),
        "handoff_manifest_path": str(handoff_manifest_path),
        "handoff_manifest_exists": True,
        "handoff_manifest_assets": len(handoff_manifest.get("assets") or []),
        "handoff_manifest_images": len(handoff_manifest.get("images") or []),
        "handoff_manifest_shots": len(handoff_manifest.get("shots") or []),
        "handoff_manifest_image_prompts": image_prompt_ready,
        "handoff_manifest_asset_identity_fields": asset_identity_ready,
        "handoff_manifest_shot_reference_images": shot_reference_images_ready,
        "handoff_manifest_production_lineage": lineage_ready,
        "handoff_ready": audit.handoff_ready,
        "asset_count": audit.asset_count,
        "shot_count": audit.shot_count,
        "embedded_images": audit.embedded_images,
        "max_table_columns": audit.max_table_columns,
        "missing_image_asset_ids": list(audit.missing_image_asset_ids),
        "structural_errors": list(audit.structural_errors),
    }
    if not result["handoff_ready"]:
        raise AssertionError(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _write_placeholder_image(path: Path, name: str, image_kind: str, asset_type: str) -> None:
    palette = {
        "character": (229, 236, 245),
        "prop": (244, 240, 232),
        "scene": (225, 232, 228),
    }
    image = Image.new("RGB", (1200, 900), palette.get(asset_type, (235, 235, 235)))
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 36, 1164, 864), outline=(49, 76, 117), width=6)
    draw.text((80, 90), f"{name}\n{image_kind}\nV2 DELIVERY FIXTURE", fill=(36, 50, 70), spacing=18)
    image.save(path, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/comic_v2_sample.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/comic_v2_verification"),
    )
    args = parser.parse_args()
    result = verify_delivery(args.fixture, args.output_dir)
    print(f"V2 delivery verified: {result['path']}")


if __name__ == "__main__":
    main()
