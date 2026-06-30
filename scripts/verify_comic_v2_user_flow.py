"""Verify the comic-production V2 flow through the public API endpoints.

This verifier is intentionally deterministic: it replaces model and image calls
with fixture-backed doubles, while still walking the same FastAPI endpoints a
user triggers from the workbench.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sqlite3
import sys
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.comic_office.v2.asset_manifest import build_asset_manifest, replace_asset_manifest
from src.comic_office.v2.contracts import build_contract_bundle
from src.comic_office.v2.production import ImageProductionResult, ImageRecord, PromptPackage
from src.comic_office.v2.prompt_director import build_asset_prompt_plan, build_shot_card
from src.image_generation import GeneratedImage
from src.web.app import app, config_manager


def verify_user_flow(fixture_path: Path, output_dir: Path, *, cleanup: bool = True) -> dict:
    """Run a full user-style V2 flow and return an auditable summary."""
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    workspace_id = f"ws_v2_flow_{uuid.uuid4().hex[:8]}"
    task_id = f"comic_v2_{workspace_id}"
    output_dir = Path(output_dir)
    visited_stages: list[str] = []

    source_story = fixture["source_story"]
    planner_payload = fixture["planner_payload"]
    bundle_v1 = build_contract_bundle(source_story, planner_payload)
    revised_payload = copy.deepcopy(planner_payload)
    revised_payload.setdefault("visual", {})["lighting"] = (
        str(revised_payload.get("visual", {}).get("lighting") or "") + "；已按用户要求强化月光与灯火对比"
    )
    bundle_v2 = build_contract_bundle(source_story, revised_payload, style_version=2)
    initial_manifest = build_asset_manifest(bundle_v2, fixture["assets"][:2])

    def record(response):
        if response.status_code >= 400:
            raise AssertionError(f"{response.request.method} {response.request.url.path} failed: {response.status_code} {response.text}")
        payload = response.json()
        stage = payload.get("stage")
        if stage:
            visited_stages.append(stage)
        return payload

    async def fake_plan_contract(*args, **kwargs):
        return bundle_v1

    async def fake_revise_visual_bible(*args, **kwargs):
        return bundle_v2

    async def fake_plan_asset_manifest(bundle, planner_config, reviewer_config, *, revision_request="", previous_manifest=None, **kwargs):
        if previous_manifest is None:
            return initial_manifest
        return replace_asset_manifest(previous_manifest, revision_request, fixture["assets"])

    async def fake_direct_asset_prompts(bundle, manifest, model_config, **kwargs):
        prompts = [
            build_asset_prompt_plan(asset, bundle.visual, image_kind=image_kind)
            for asset in manifest.items
            for image_kind in asset.planned_images
        ]
        package_raw = json.dumps(
            {
                "story_id": bundle.creative.story_id,
                "style_id": bundle.visual.style_id,
                "manifest_hash": manifest.manifest_hash,
                "prompts": [prompt.__dict__ for prompt in prompts],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return PromptPackage(
            package_id=f"userflow_prompts_{hashlib.sha256(package_raw.encode('utf-8')).hexdigest()[:12]}",
            story_id=bundle.creative.story_id,
            story_version=bundle.creative.story_version,
            style_id=bundle.visual.style_id,
            style_version=bundle.visual.style_version,
            manifest_id=manifest.manifest_id,
            manifest_version=manifest.version,
            prompts=tuple(prompts),
        )

    async def fake_direct_shot_cards(bundle, manifest, prompt_package, model_config, **kwargs):
        by_name = {asset.name: asset for asset in manifest.items}
        shots = [
            build_shot_card(
                payload,
                characters=[by_name[name] for name in payload.get("characters", [])],
                props=[by_name[name] for name in payload.get("props", [])],
                scene=by_name[payload["scene"]],
                visual=bundle.visual,
            )
            for payload in fixture["shots"]
        ]
        return replace(prompt_package, shots=tuple(shots))

    async def fake_produce_asset_images(prompt_package, manifest, visual, image_config, review_config, out_dir, **kwargs):
        out_dir = Path(out_dir)
        records = []
        for asset in manifest.items:
            baseline_id = ""
            for index, image_kind in enumerate(asset.planned_images):
                prompt = build_asset_prompt_plan(asset, visual, image_kind=image_kind)
                image_id = f"img_{asset.asset_id}_{image_kind}"
                image_path = out_dir / f"{asset.asset_id}_{image_kind}.png"
                _write_placeholder_image(image_path, asset.name, image_kind, asset.asset_type)
                records.append(ImageRecord(
                    image_id=image_id,
                    asset_id=asset.asset_id,
                    image_kind=image_kind,
                    prompt_hash=hashlib.sha256(prompt.render().encode("utf-8")).hexdigest(),
                    path=str(image_path),
                    provider="fixture",
                    model="deterministic-placeholder",
                    attempts=1,
                    status="approved",
                    is_identity_baseline=index == 0,
                    reference_image_ids=() if index == 0 else (baseline_id,),
                    story_id=prompt_package.story_id,
                    story_version=prompt_package.story_version,
                    style_id=prompt_package.style_id,
                    style_version=prompt_package.style_version,
                    manifest_version=prompt_package.manifest_version,
                    review={"status": "pass", "fixture": True},
                ))
                if index == 0:
                    baseline_id = image_id
        return ImageProductionResult(
            status="ready_for_delivery",
            production_ready=True,
            records=tuple(records),
            failures=(),
        )

    config_manager.create_workspace(
        workspace_id=workspace_id,
        office_id="comic_production",
        title=f"V2 user flow {workspace_id}",
        brief=source_story[:160],
    )
    config_manager.create_task_run(task_id, f"Verify comic V2 user flow for {workspace_id}", "")
    confirmed = {
        "title": planner_payload.get("title", "V2 story"),
        "story_draft": source_story,
        "script_hash": hashlib.sha256(source_story.encode("utf-8")).hexdigest()[:16],
        "script_version": 1,
    }
    config_manager.set_kv(
        f"comic_cabinet_session:{workspace_id}",
        json.dumps({"confirmed": True, "confirmed_script": confirmed}, ensure_ascii=False),
    )
    config_manager.create_artifact(
        artifact_id=f"art_{workspace_id}_confirmed_script",
        workspace_id=workspace_id,
        task_id="",
        artifact_type="confirmed_script",
        title=f"{confirmed['title']} - confirmed script",
        content=source_story,
        metadata={"office_id": "comic_production", **confirmed, "confirmed": True},
        created_by="shangshu",
    )

    client = TestClient(app)
    try:
        with (
            patch("src.web.app.plan_contract", side_effect=fake_plan_contract),
            patch("src.web.app.revise_visual_bible", side_effect=fake_revise_visual_bible),
            patch("src.web.app.plan_asset_manifest", side_effect=fake_plan_asset_manifest),
            patch("src.web.app.direct_asset_prompts", side_effect=fake_direct_asset_prompts),
            patch("src.web.app.direct_shot_cards", side_effect=fake_direct_shot_cards),
            patch("src.web.app.produce_asset_images", side_effect=fake_produce_asset_images),
        ):
            record(client.post(f"/api/workspaces/{workspace_id}/comic/v2/plan-confirmed", json={}))
            record(client.post(
                f"/api/workspaces/{workspace_id}/comic/v2/visual-bible/revise",
                json={"revision_request": "强化古风月光，不允许现代质感。"},
            ))
            record(client.post(f"/api/workspaces/{workspace_id}/comic/v2/visual-bible/approve", json={}))
            record(client.post(f"/api/workspaces/{workspace_id}/comic/v2/assets/plan", json={}))
            record(client.post(
                f"/api/workspaces/{workspace_id}/comic/v2/assets/revise",
                json={"revision_request": "补齐故事里出现的场景资产，保留人物和道具。"},
            ))
            record(client.post(f"/api/workspaces/{workspace_id}/comic/v2/assets/approve", json={}))
            record(client.post(f"/api/workspaces/{workspace_id}/comic/v2/prompts/plan", json={}))
            record(client.post(f"/api/workspaces/{workspace_id}/comic/v2/images/generate", json={}))
            ready = record(client.post(f"/api/workspaces/{workspace_id}/comic/v2/delivery/build", json={}))

        delivery = ready.get("delivery") or {}
        uri = delivery.get("uri") or ""
        if not uri:
            raise AssertionError("delivery did not expose a download uri")
        download = client.get(uri)
        if download.status_code != 200:
            raise AssertionError(f"download failed: {download.status_code} {download.text[:200]}")

        artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
        image_count = len([item for item in artifacts if item["artifact_type"] == "comic_v2_generated_image"])
        handoff_manifest_uri = delivery.get("handoff_manifest_uri") or ""
        handoff_manifest = next(
            (
                item for item in artifacts
                if item.get("artifact_type") == "comic_v2_handoff_manifest"
                and item.get("uri") == handoff_manifest_uri
            ),
            {},
        )
        handoff_lineage = (handoff_manifest.get("metadata") or {}).get("production_lineage") or []
        manifest_assets = (handoff_manifest.get("metadata") or {}).get("assets") or []
        asset_baseline_chain_ready = (
            isinstance(manifest_assets, list)
            and bool(manifest_assets)
            and all(
                isinstance(asset, dict)
                and bool(asset.get("identity_baseline_image_id"))
                and bool(asset.get("identity_baseline_image_kind"))
                and asset.get("identity_baseline_image_id") in set(asset.get("image_ids") or [])
                and asset.get("identity_baseline_image_id") in set((asset.get("image_ids_by_kind") or {}).values())
                for asset in manifest_assets
            )
        )
        lineage_handoff_ready = (
            isinstance(handoff_lineage, list)
            and bool(handoff_lineage)
            and all(
                isinstance(item, dict)
                and bool(item.get("handoff_to"))
                and bool(item.get("acceptance_criteria"))
                for item in handoff_lineage
            )
        )
        config_manager.update_task_run(
            task_id,
            "completed",
            current_phase="ready_for_handoff",
            result={"final_stage": ready.get("stage"), "delivery_uri": uri},
            completed=True,
        )
        run = config_manager.get_task_run(task_id)
        summary = {
            "workspace_id": workspace_id,
            "final_stage": ready.get("stage"),
            "visited_stages": visited_stages,
            "visual_revisions": len([stage for stage in visited_stages if stage == "visual_bible_review"]) - 1,
            "asset_revisions": max(0, len([stage for stage in visited_stages if stage == "asset_review"]) - 1),
            "generated_images": image_count,
            "download_uri": uri,
            "handoff_manifest_uri": handoff_manifest_uri,
            "handoff_manifest_artifact": bool(handoff_manifest),
            "handoff_manifest_production_lineage": bool(handoff_lineage),
            "handoff_manifest_asset_baseline_chain": asset_baseline_chain_ready,
            "production_lineage_handoff_fields": lineage_handoff_ready,
            "production_lineage_stages": [
                item.get("stage", "")
                for item in handoff_lineage
                if isinstance(item, dict) and item.get("stage")
            ],
            "download_bytes": len(download.content),
            "delivery_audit": delivery.get("audit") or {},
            "artifact_count": len(artifacts),
            "event_count": len(run.get("events", [])),
            "task_status": run.get("status", ""),
        }
        if summary["final_stage"] != "ready_for_handoff":
            raise AssertionError(json.dumps(summary, ensure_ascii=False, indent=2))
        if not summary["delivery_audit"].get("handoff_ready"):
            raise AssertionError(json.dumps(summary, ensure_ascii=False, indent=2))
        if not summary["production_lineage_handoff_fields"]:
            raise AssertionError(json.dumps(summary, ensure_ascii=False, indent=2))
        if not summary["handoff_manifest_asset_baseline_chain"]:
            raise AssertionError(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    finally:
        if cleanup:
            _cleanup_workspace(workspace_id, output_dir)


def _write_placeholder_image(path: Path, name: str, image_kind: str, asset_type: str) -> GeneratedImage:
    path.parent.mkdir(parents=True, exist_ok=True)
    palette = {
        "character": (246, 247, 250),
        "prop": (248, 247, 243),
        "scene": (225, 232, 228),
    }
    image = Image.new("RGB", (1200, 900), palette.get(asset_type, (240, 240, 240)))
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 36, 1164, 864), outline=(49, 76, 117), width=6)
    draw.text((80, 90), f"{name}\n{image_kind}\nV2 USER FLOW", fill=(36, 50, 70), spacing=18)
    image.save(path, format="PNG")
    return GeneratedImage(title=f"{name}-{image_kind}", prompt="", path=str(path), provider="fixture", model="placeholder")


def _cleanup_workspace(workspace_id: str, output_dir: Path) -> None:
    conn = sqlite3.connect("user_data/config.db")
    try:
        conn.execute("DELETE FROM artifacts WHERE workspace_id=?", (workspace_id,))
        conn.execute("DELETE FROM workspaces WHERE workspace_id=?", (workspace_id,))
        conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_v2_state:{workspace_id}",))
        conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_cabinet_session:{workspace_id}",))
        conn.execute("DELETE FROM task_runs WHERE task_id=?", (f"comic_v2_{workspace_id}",))
        conn.execute("DELETE FROM task_events WHERE task_id=?", (f"comic_v2_{workspace_id}",))
        conn.commit()
    finally:
        conn.close()
    shutil.rmtree(Path("output") / "workspaces" / workspace_id, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/comic_v2_sample.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/comic_v2_user_flow_verification"))
    parser.add_argument("--keep-workspace", action="store_true", help="Leave the generated workspace in local storage for browser inspection.")
    args = parser.parse_args()
    result = verify_user_flow(args.fixture, args.output_dir, cleanup=not args.keep_workspace)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
