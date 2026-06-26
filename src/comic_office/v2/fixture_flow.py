"""Local fixture-mode production helpers for V2 end-to-end verification."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .asset_manifest import AssetManifest, build_asset_manifest, replace_asset_manifest
from .contracts import ContractBundle, build_contract_bundle
from .production import ImageProductionResult, ImageRecord, PromptPackage
from .prompt_director import build_asset_prompt_plan, build_shot_card


def fixture_mode_enabled() -> bool:
    return os.getenv("COMIC_V2_FIXTURE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def fixture_contract_bundle(
    source_story: str,
    *,
    story_version: int = 1,
    style_version: int = 1,
    revision_request: str = "",
) -> ContractBundle:
    fixture = _load_fixture()
    story = source_story if _fixture_quotes_match(source_story, fixture) else fixture["source_story"]
    payload = json.loads(json.dumps(fixture["planner_payload"], ensure_ascii=False))
    note = revision_request.strip()
    if note:
        visual = payload["visual"]
        visual["lighting"] = f"{visual['lighting']}；本轮退回要求：{note}"
        visual["visual_motifs"] = list(dict.fromkeys([*visual.get("visual_motifs", []), "退回后强化的统一视觉锚点"]))
    return build_contract_bundle(
        story,
        payload,
        source_mode="full_story",
        story_version=story_version,
        style_version=style_version,
    )


def fixture_initial_manifest(bundle: ContractBundle) -> AssetManifest:
    assets = _load_fixture()["assets"][:2]
    return build_asset_manifest(bundle, assets)


def fixture_revised_manifest(
    bundle: ContractBundle,
    previous: AssetManifest,
    revision_request: str,
) -> AssetManifest:
    return replace_asset_manifest(
        previous,
        revision_request or "按用户退回意见补齐资产拆解",
        _load_fixture()["assets"],
    )


def fixture_prompt_package(bundle: ContractBundle, manifest: AssetManifest) -> PromptPackage:
    prompts = [
        build_asset_prompt_plan(asset, bundle.visual, image_kind=image_kind)
        for asset in manifest.items
        for image_kind in asset.planned_images
    ]
    by_name = {item.name: item for item in manifest.items}
    shots = []
    for raw in _load_fixture()["shots"]:
        scene = by_name[str(raw["scene"])]
        characters = [by_name[str(name)] for name in raw.get("characters", []) if str(name) in by_name]
        props = [by_name[str(name)] for name in raw.get("props", []) if str(name) in by_name]
        payload = {
            "shot_id": raw["shot_id"],
            "scene_id": raw["scene_id"],
            "story_beat": raw["story_beat"],
            "scene_asset_id": scene.asset_id,
            "character_asset_ids": [item.asset_id for item in characters],
            "prop_asset_ids": [item.asset_id for item in props],
            "evidence_quote": raw["evidence_quote"],
            "action_chain": raw["action_chain"],
            "performance_intent": raw["performance_intent"],
            "framing": raw["framing"],
            "camera_movement": raw["camera_movement"],
            "lighting": raw["lighting"],
            "dialogue": raw["dialogue"],
            "sound": raw["sound"],
            "retry_strategy": raw["retry_strategy"],
        }
        shots.append(build_shot_card(payload, characters=characters, props=props, scene=scene, visual=bundle.visual))
    package_raw = json.dumps(
        {
            "story_id": bundle.creative.story_id,
            "style_id": bundle.visual.style_id,
            "manifest_hash": manifest.manifest_hash,
            "prompts": [asdict(prompt) for prompt in prompts],
            "shots": [asdict(shot) for shot in shots],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return PromptPackage(
        package_id=f"fixture_prompts_{hashlib.sha256(package_raw.encode('utf-8')).hexdigest()[:12]}",
        story_id=bundle.creative.story_id,
        story_version=bundle.creative.story_version,
        style_id=bundle.visual.style_id,
        style_version=bundle.visual.style_version,
        manifest_id=manifest.manifest_id,
        manifest_version=manifest.version,
        prompts=tuple(prompts),
        shots=tuple(shots),
    )


def fixture_image_production(
    package: PromptPackage,
    manifest: AssetManifest,
    output_dir: Path,
) -> ImageProductionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[ImageRecord] = []
    prompt_lookup = {(prompt.object_id, prompt.image_kind): prompt for prompt in package.prompts}
    approved_by_asset: dict[str, list[str]] = {}
    for asset in manifest.items:
        for index, image_kind in enumerate(asset.planned_images):
            prompt = prompt_lookup[(asset.asset_id, image_kind)]
            image_id = f"img_{asset.asset_id}_{image_kind}"
            image_path = output_dir / f"{image_id}.png"
            _write_fixture_image(image_path, title=asset.name, subtitle=image_kind, asset_type=asset.asset_type)
            references = tuple(approved_by_asset.get(asset.asset_id, [])[:1])
            record = ImageRecord(
                image_id=image_id,
                asset_id=asset.asset_id,
                image_kind=image_kind,
                prompt_hash=hashlib.sha256(prompt.render().encode("utf-8")).hexdigest(),
                path=str(image_path),
                provider="fixture",
                model="local-fixture",
                attempts=1,
                status="approved",
                is_identity_baseline=index == 0,
                reference_image_ids=references,
                story_id=package.story_id,
                story_version=package.story_version,
                style_id=package.style_id,
                style_version=package.style_version,
                manifest_version=package.manifest_version,
                review={
                    "status": "approved",
                    "handoff_ready": True,
                    "issues": [],
                    "revision_prompt": "",
                    "summary": "本地验证模式自动通过，用于测试流程与文档结构。",
                },
            )
            records.append(record)
            approved_by_asset.setdefault(asset.asset_id, []).append(record.image_id)
    return ImageProductionResult(
        status="ready_for_delivery",
        production_ready=True,
        records=tuple(records),
        failures=(),
    )


def _load_fixture() -> dict[str, Any]:
    path = Path(os.getenv("COMIC_V2_FIXTURE_PATH", "tests/fixtures/comic_v2_sample.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_quotes_match(source_story: str, fixture: dict[str, Any]) -> bool:
    source = source_story or ""
    episode_quotes = [
        str(item.get("evidence_quote") or "")
        for item in fixture.get("planner_payload", {}).get("episodes", [])
    ]
    asset_quotes = [str(item.get("evidence_quote") or "") for item in fixture.get("assets", [])]
    shot_quotes = [str(item.get("evidence_quote") or "") for item in fixture.get("shots", [])]
    return all(quote and quote in source for quote in [*episode_quotes, *asset_quotes, *shot_quotes])


def _write_fixture_image(path: Path, *, title: str, subtitle: str, asset_type: str) -> None:
    if asset_type in {"character", "prop"}:
        background = (250, 250, 248)
        accent = (46, 76, 117)
    else:
        background = (38, 50, 70)
        accent = (229, 238, 245)
    image = Image.new("RGB", (960, 1280), background)
    draw = ImageDraw.Draw(image)
    margin = 96
    draw.rectangle((margin, margin, 960 - margin, 1280 - margin), outline=accent, width=8)
    draw.ellipse((330, 310, 630, 610), outline=accent, width=10)
    draw.rectangle((380, 640, 580, 980), outline=accent, width=10)
    draw.text((margin + 28, 1040), title, fill=accent)
    draw.text((margin + 28, 1096), subtitle, fill=accent)
    image.save(path)
