"""Verify public no-key demo endpoints, showcase manifest, and downloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from src.web.app import app


DEMO_ENDPOINTS = {
    "comic_production": {
        "name": "AI 漫剧制片办公室",
        "endpoint": "/api/demo/comic-production",
        "launch_gate_endpoint": "/api/offices/comic_production/launch-gates",
    },
    "research": {
        "name": "研究办公室",
        "endpoint": "/api/demo/research",
        "launch_gate_endpoint": "/api/offices/research/launch-gates",
    },
}


def _download_items(payload: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for item in payload.get("deliverables") or payload.get("artifacts") or []:
        uri = item.get("uri") or ""
        status = item.get("status") or ""
        if uri.startswith("/api/demo/") and status == "downloadable":
            items.append({
                "title": str(item.get("title") or item.get("type") or uri),
                "uri": uri,
            })
    return items


def _collect_launch_gate_links(client: TestClient, endpoint: str) -> list[str]:
    response = client.get(endpoint)
    if response.status_code != 200:
        return []
    links: list[str] = []
    for gate in response.json().get("gates", []):
        for link in gate.get("evidence_links", []):
            uri = link.get("uri")
            if uri:
                links.append(str(uri))
    return links


def _verify_showcase_manifest(client: TestClient, errors: list[str]) -> dict[str, Any]:
    response = client.get("/api/demo/public-showcase")
    if response.status_code != 200:
        errors.append(f"public showcase manifest returned {response.status_code}")
        return {
            "status_code": response.status_code,
            "mode": "",
            "audience_path_count": 0,
            "featured_demo_count": 0,
        }

    payload = response.json()
    audience_paths = payload.get("audience_paths") or []
    featured_demos = payload.get("featured_demos") or []
    portfolio_embed = payload.get("portfolio_embed") or {}
    public_deployment = payload.get("public_deployment") or {}
    static_export = public_deployment.get("static_export") or {}
    fast_review_route = portfolio_embed.get("fast_review_route") or []
    interview_script = portfolio_embed.get("interview_demo_script") or []
    reproducibility = portfolio_embed.get("reproducibility_checklist") or []
    downstream_quick_start = portfolio_embed.get("downstream_quick_start") or []
    asset_requirement_matrix = portfolio_embed.get("asset_requirement_matrix") or {}
    asset_image_production_spec = portfolio_embed.get("asset_image_production_spec") or {}
    release_badge = portfolio_embed.get("release_badge") or {}
    handoff_inventory = portfolio_embed.get("handoff_inventory") or {}
    real_production_claim = portfolio_embed.get("real_production_claim") or {}
    quality_upgrade_path = portfolio_embed.get("quality_upgrade_path") or {}
    portfolio_integration = portfolio_embed.get("portfolio_integration") or {}
    portfolio_ci_proof = portfolio_integration.get("portfolio_ci_proof") or {}
    deployment_ci_verification = public_deployment.get("ci_verification") or {}
    office_extension_story = portfolio_embed.get("office_extension_story") or {}
    if payload.get("mode") != "public_no_key_showcase":
        errors.append("public showcase manifest has unexpected mode")
    if payload.get("requires_api_key") is not False:
        errors.append("public showcase manifest must not require API key")
    if payload.get("calls_real_models") is not False:
        errors.append("public showcase manifest must not call real models")
    if len(audience_paths) < 3:
        errors.append("public showcase manifest needs at least 3 audience paths")
    if len(featured_demos) < 2:
        errors.append("public showcase manifest needs at least 2 featured demos")
    if not portfolio_embed.get("repository_url"):
        errors.append("public showcase manifest must expose a repository URL for portfolio pages")
    if len(portfolio_embed.get("sample_deliverables") or []) < 5:
        errors.append("portfolio embed must expose at least 5 sample deliverables, including the real production claim report")
    for item in portfolio_embed.get("sample_deliverables") or []:
        if not item.get("reader_guidance"):
            errors.append(f"sample deliverable missing reader guidance: {item.get('title') or item.get('uri')}")
        if len(item.get("acceptance_signals") or []) < 3:
            errors.append(f"sample deliverable missing acceptance signals: {item.get('title') or item.get('uri')}")
    if [item.get("order") for item in fast_review_route] != [1, 2, 3, 4, 5]:
        errors.append("portfolio embed must expose a 5-step fast review route")
    fast_review_text = json.dumps(fast_review_route, ensure_ascii=False)
    for marker in ("asset-matrix-title", "three_view", "clean_background_required"):
        if marker not in fast_review_text:
            errors.append(f"fast review route is missing marker: {marker}")
    reading_guide = portfolio_embed.get("deliverable_reading_guide") or []
    if len(reading_guide) < 4:
        errors.append("portfolio embed must expose a 4-step deliverable reading guide")
    for item in reading_guide:
        if not str(item.get("uri") or "").startswith("/api/demo/"):
            errors.append(f"reading guide item has invalid demo uri: {item.get('title') or item.get('uri')}")
        if not item.get("look_for") or not item.get("proves"):
            errors.append(f"reading guide item missing look_for/proves: {item.get('title') or item.get('uri')}")
    if len(reproducibility) < 5:
        errors.append("portfolio embed must expose a 5-step reproducibility checklist")
    for item in reproducibility:
        if not item.get("command") or not item.get("expected") or not item.get("if_fails"):
            errors.append(f"reproducibility checklist item missing command/expected/if_fails: {item.get('title')}")
    if not any("verify_release_readiness.py" in str(item.get("command") or "") for item in reproducibility):
        errors.append("reproducibility checklist must include the release readiness gate")
    if [item.get("step") for item in downstream_quick_start] != [1, 2, 3, 4, 5]:
        errors.append("portfolio embed must expose a 5-step downstream quick-start")
    for item in downstream_quick_start:
        if (
            not item.get("owner")
            or len(item.get("input_refs") or []) < 2
            or not item.get("action")
            or not item.get("output")
            or not item.get("acceptance")
        ):
            errors.append(f"downstream quick-start item is incomplete: {item.get('title') or item.get('step')}")
    if asset_requirement_matrix.get("ready_assets") != asset_requirement_matrix.get("total_assets"):
        errors.append("portfolio asset requirement matrix must mark every demo asset ready")
    if asset_requirement_matrix.get("missing_required_images") not in (0, None):
        errors.append("portfolio asset requirement matrix must not miss required images")
    asset_matrix_text = json.dumps(asset_requirement_matrix, ensure_ascii=False)
    for marker in ("three_view", "expression_sheet", "turnaround", "top_down", "clean_background_required"):
        if marker not in asset_matrix_text:
            errors.append(f"portfolio asset requirement matrix is missing marker: {marker}")
    asset_spec_types = {
        item.get("asset_type"): item
        for item in asset_image_production_spec.get("asset_types") or []
    }
    if set(asset_spec_types) != {"character", "prop", "scene"}:
        errors.append("portfolio asset image production spec must cover character, prop, and scene assets")
    asset_spec_text = json.dumps(asset_image_production_spec, ensure_ascii=False)
    for marker in (
        "clean_white_or_near_white_background",
        "spatial_environment_not_white_background",
        "three_view",
        "expression_sheet",
        "turnaround",
        "top_down",
        "不要把人物放进完整剧情场面",
        "不要把场景做成白底静物",
        "verify_comic_v2_downstream_handoff.py",
    ):
        if marker not in asset_spec_text:
            errors.append(f"portfolio asset image production spec is missing marker: {marker}")
    if release_badge.get("status") != "safe_public_demo":
        errors.append("portfolio embed must expose a safe_public_demo release badge")
    if release_badge.get("mode") != "demo_only":
        errors.append("release badge must clearly state demo_only mode")
    if release_badge.get("can_claim_real_quality") is not False:
        errors.append("release badge must not claim real model visual quality")
    if "verify_release_readiness.py" not in str(release_badge.get("primary_gate") or ""):
        errors.append("release badge must point to the release readiness gate")
    if len(release_badge.get("signals") or []) < 5:
        errors.append("release badge must include at least five public safety signals")
    if not any((item.get("kind") == "screenshot_target") for item in portfolio_embed.get("workflow_showcase") or []):
        errors.append("portfolio embed must include screenshot targets for the main workflow")
    if handoff_inventory.get("uri") != "/api/demo/comic-production/handoff-inventory":
        errors.append("portfolio embed must expose the comic handoff inventory endpoint")
    if handoff_inventory.get("production_verified_count") not in (0, None):
        errors.append("public showcase must not claim real comic production verification from demo inventory")
    if not handoff_inventory.get("safe_public_claim"):
        errors.append("portfolio embed handoff inventory must include a safe public claim")
    if handoff_inventory.get("demo_only_count", 0) > 0:
        if handoff_inventory.get("image_quality_item_count", 0) <= 0:
            errors.append("portfolio embed handoff inventory must summarize image quality items")
        if handoff_inventory.get("total_images", 0) <= 0:
            errors.append("portfolio embed handoff inventory must summarize total images")
        if "usable_images" not in handoff_inventory:
            errors.append("portfolio embed handoff inventory must summarize usable images")
        if "waste_or_rework_images" not in handoff_inventory:
            errors.append("portfolio embed handoff inventory must summarize waste/rework images")
        if "waste_or_rework_rate" not in handoff_inventory:
            errors.append("portfolio embed handoff inventory must summarize waste/rework rate")
    if real_production_claim.get("uri") != "/api/demo/comic-production/claim-report":
        errors.append("portfolio embed must expose the comic real production claim report endpoint")
    if real_production_claim.get("claim_level") != "demo_structure_only":
        errors.append("public showcase fixed sample must remain demo_structure_only")
    if real_production_claim.get("can_claim_real_quality") is not False:
        errors.append("public showcase must not claim real production quality from the fixed sample")
    if not real_production_claim.get("forbidden_public_claims"):
        errors.append("real production claim report must include forbidden public claims")
    if quality_upgrade_path.get("current_public_level") != "demo_structure_only":
        errors.append("portfolio embed quality upgrade path must start from demo_structure_only")
    if quality_upgrade_path.get("current_image_evidence") != "fixture_only":
        errors.append("portfolio embed quality upgrade path must expose fixture_only as the public image evidence")
    if quality_upgrade_path.get("can_claim_real_quality") is not False:
        errors.append("portfolio embed quality upgrade path must not claim real quality in public demo")
    if quality_upgrade_path.get("recovery_action") != "regenerate_images":
        errors.append("portfolio embed quality upgrade path must point to regenerate_images")
    if quality_upgrade_path.get("trace_endpoint") != "/api/tasks/{task_id}/comic-v2-trace.json":
        errors.append("portfolio embed quality upgrade path must expose the history trace endpoint")
    if len(quality_upgrade_path.get("steps") or []) < 3:
        errors.append("portfolio embed quality upgrade path must include at least three operator steps")
    for item in quality_upgrade_path.get("steps") or []:
        if not item.get("owner") or not item.get("action") or not item.get("evidence") or not item.get("expected"):
            errors.append(f"quality upgrade path step is incomplete: {item.get('order') or item.get('owner')}")
    if portfolio_integration.get("recommended_path") != "static_export":
        errors.append("portfolio integration must recommend static_export for public websites")
    integration_static = portfolio_integration.get("static_export") or {}
    if integration_static.get("source_dir") != "dist/public-showcase":
        errors.append("portfolio integration must use dist/public-showcase as the static source")
    if integration_static.get("requires_backend") is not False or integration_static.get("requires_api_key") is not False:
        errors.append("portfolio integration static export must be backend-free and no-key")
    integration_options = portfolio_integration.get("integration_options") or []
    option_ids = {item.get("id") for item in integration_options}
    if {"standalone_static_site", "personal_site_subdirectory"} - option_ids:
        errors.append("portfolio integration must document standalone and personal-site-subdirectory options")
    if "public/three-stooges/" not in json.dumps(integration_options, ensure_ascii=False):
        errors.append("portfolio integration must show the personal website copy target")
    forbidden = "\n".join(portfolio_integration.get("must_not_include") or [])
    for marker in ("config.yaml", "API Key", "Cookie", "user_data/", "output/"):
        if marker not in forbidden:
            errors.append(f"portfolio integration must forbid {marker}")
    commands = "\n".join(portfolio_integration.get("verification_commands") or [])
    for marker in ("export_public_showcase.py", "verify_static_public_showcase.py", "verify_release_readiness.py", "check_no_secrets.py"):
        if marker not in commands:
            errors.append(f"portfolio integration must include verifier command: {marker}")
    if portfolio_ci_proof.get("status") != "repo_static_checks":
        errors.append("portfolio integration must expose repository static CI proof")
    if portfolio_ci_proof.get("workflow_path") != ".github/workflows/three-cobblers-showcase.yml":
        errors.append("portfolio CI proof must point to the personal website showcase workflow")
    ci_commands = "\n".join(portfolio_ci_proof.get("commands") or [])
    for marker in ("npm run check:showcase", "npm run check:deploy-handoff", "npm run build"):
        if marker not in ci_commands:
            errors.append(f"portfolio CI proof must include command: {marker}")
    ci_boundary = json.dumps(portfolio_ci_proof, ensure_ascii=False)
    for marker in ("Vercel production route", "real model calls", "npm run check:online"):
        if marker not in ci_boundary:
            errors.append(f"portfolio CI proof must preserve boundary marker: {marker}")
    starter_checklist = office_extension_story.get("starter_checklist") or []
    future_candidates = office_extension_story.get("future_office_candidates") or []
    future_backlog = office_extension_story.get("future_platform_backlog") or []
    office_launch_matrix = portfolio_embed.get("office_launch_matrix") or {}
    launch_matrix_summary = office_launch_matrix.get("summary") or {}
    launch_matrix_offices = office_launch_matrix.get("offices") or []
    if office_extension_story.get("starter_checklist_doc") != "docs/NEW_OFFICE_STARTER_CHECKLIST.md":
        errors.append("portfolio embed must expose the new office starter checklist document")
    if len(starter_checklist) != 8:
        errors.append("portfolio embed must expose the 8-step new office starter checklist")
    starter_phases = {item.get("phase") for item in starter_checklist}
    for phase in ("product", "safety", "isolation", "workflow", "demo", "quality", "public_demo", "release"):
        if phase not in starter_phases:
            errors.append(f"office extension story is missing phase: {phase}")
    for item in starter_checklist:
        if not item.get("id") or not item.get("question") or not item.get("evidence"):
            errors.append(f"office extension checklist item is incomplete: {item.get('id') or item.get('order')}")
    extension_commands = "\n".join(office_extension_story.get("required_verifiers") or [])
    for marker in ("verify_office_isolation.py", "verify_office_extension_governance.py", "verify_release_readiness.py", "check_no_secrets.py"):
        if marker not in extension_commands:
            errors.append(f"office extension story must include verifier command: {marker}")
    candidate_ids = {item.get("id") for item in future_candidates}
    for candidate_id in ("short_video_ads", "ecommerce_selection", "story_ip", "technical_project"):
        if candidate_id not in candidate_ids:
            errors.append(f"office extension story is missing future office candidate: {candidate_id}")
    for item in future_candidates:
        if not item.get("user_job") or not item.get("not_ready_reason") or not item.get("required_before_public"):
            errors.append(f"future office candidate is incomplete: {item.get('id')}")
    backlog_ids = {item.get("id") for item in future_backlog}
    for backlog_id in ("future_schema_validators", "future_recovery_events"):
        if backlog_id not in backlog_ids:
            errors.append(f"office extension story is missing future platform backlog: {backlog_id}")
    for item in future_backlog:
        if not item.get("description") or not item.get("evidence_required"):
            errors.append(f"future platform backlog item is incomplete: {item.get('id')}")
    if launch_matrix_summary.get("office_count") != 3:
        errors.append("public showcase should expose all current office launch states")
    if launch_matrix_summary.get("primary_allowed_count") != 1:
        errors.append("public showcase should expose exactly one primary office")
    launch_by_office = {item.get("office_id"): item for item in launch_matrix_offices}
    if launch_by_office.get("comic_production", {}).get("primary_allowed") is not True:
        errors.append("public showcase should mark comic_production as the primary office")
    if launch_by_office.get("comic", {}).get("visitor_label") != "旧版兼容入口":
        errors.append("public showcase should label legacy comic as a compatibility entry")
    if "legacy_migration_required" not in (launch_by_office.get("comic", {}).get("blocked_by") or []):
        errors.append("public showcase should expose the legacy comic migration blocker")
    if len(interview_script) < 4:
        errors.append("portfolio embed must expose a 4-step interview demo script")
    for item in interview_script:
        if not item.get("visitor_action") or not item.get("product_response") or not item.get("proof") or not item.get("boundary"):
            errors.append(f"interview demo script item is incomplete: {item.get('title') or item.get('order')}")
    if public_deployment.get("mode") != "demo_only":
        errors.append("public deployment profile must be demo_only")
    if public_deployment.get("allows_real_model_calls") is not False:
        errors.append("public deployment profile must forbid real model calls")
    if public_deployment.get("allows_workspace_writes") is not False:
        errors.append("public deployment profile must forbid workspace writes")
    if deployment_ci_verification.get("workflow_path") != ".github/workflows/three-cobblers-showcase.yml":
        errors.append("public deployment profile must expose the personal website CI workflow path")
    if deployment_ci_verification.get("live_authority") != "npm run check:online":
        errors.append("public deployment CI verification must defer live proof to check:online")
    if static_export.get("command") != "python scripts/export_public_showcase.py":
        errors.append("public deployment profile must expose the static export command")
    if static_export.get("entrypoint") != "dist/public-showcase/index.html":
        errors.append("public deployment profile must expose the static showcase entrypoint")
    if static_export.get("requires_backend") is not False or static_export.get("requires_api_key") is not False:
        errors.append("static showcase export must be backend-free and no-key")

    return {
        "status_code": response.status_code,
        "mode": payload.get("mode", ""),
        "product_name": payload.get("product_name", ""),
        "audience_path_count": len(audience_paths),
        "featured_demo_count": len(featured_demos),
        "safe_for_public_portfolio": bool(payload.get("safe_for_public_portfolio")),
        "portfolio_deliverable_count": len(portfolio_embed.get("sample_deliverables") or []),
        "deliverables_with_reader_guidance": sum(
            1
            for item in portfolio_embed.get("sample_deliverables") or []
            if item.get("reader_guidance") and len(item.get("acceptance_signals") or []) >= 3
        ),
        "fast_review_count": len(fast_review_route),
        "fast_review_ready_count": sum(
            1
            for item in fast_review_route
            if item.get("viewer_action") and item.get("proof") and item.get("next_anchor")
        ),
        "reading_guide_count": len(reading_guide),
        "reading_guide_ready_count": sum(
            1
            for item in reading_guide
            if str(item.get("uri") or "").startswith("/api/demo/") and item.get("look_for") and item.get("proves")
        ),
        "interview_script_count": len(interview_script),
        "interview_script_ready_count": sum(
            1
            for item in interview_script
            if item.get("visitor_action") and item.get("product_response") and item.get("proof") and item.get("boundary")
        ),
        "reproducibility_count": len(reproducibility),
        "reproducibility_ready_count": sum(
            1
            for item in reproducibility
            if item.get("command") and item.get("expected") and item.get("if_fails")
        ),
        "downstream_quick_start_count": len(downstream_quick_start),
        "downstream_quick_start_ready_count": sum(
            1
            for item in downstream_quick_start
            if item.get("owner")
            and len(item.get("input_refs") or []) >= 2
            and item.get("action")
            and item.get("output")
            and item.get("acceptance")
        ),
        "release_badge_status": release_badge.get("status", ""),
        "release_badge_signal_count": len(release_badge.get("signals") or []),
        "release_badge_claim_real_quality": release_badge.get("can_claim_real_quality"),
        "handoff_inventory_uri": handoff_inventory.get("uri", ""),
        "handoff_inventory_manifest_count": handoff_inventory.get("manifest_count", 0),
        "handoff_inventory_production_verified_count": handoff_inventory.get("production_verified_count", 0),
        "handoff_inventory_image_quality_item_count": handoff_inventory.get("image_quality_item_count", 0),
        "handoff_inventory_total_images": handoff_inventory.get("total_images", 0),
        "handoff_inventory_usable_images": handoff_inventory.get("usable_images", 0),
        "handoff_inventory_waste_or_rework_images": handoff_inventory.get("waste_or_rework_images", 0),
        "handoff_inventory_waste_or_rework_rate": handoff_inventory.get("waste_or_rework_rate", 0),
        "handoff_inventory_safe_public_claim": handoff_inventory.get("safe_public_claim", ""),
        "real_production_claim_uri": real_production_claim.get("uri", ""),
        "real_production_claim_level": real_production_claim.get("claim_level", ""),
        "real_production_can_claim_real_quality": real_production_claim.get("can_claim_real_quality"),
        "quality_upgrade_recovery_action": quality_upgrade_path.get("recovery_action", ""),
        "quality_upgrade_step_count": len(quality_upgrade_path.get("steps") or []),
        "portfolio_integration_option_count": len(integration_options),
        "portfolio_integration_source_dir": integration_static.get("source_dir", ""),
        "portfolio_ci_status": portfolio_ci_proof.get("status", ""),
        "portfolio_ci_workflow": portfolio_ci_proof.get("workflow_path", ""),
        "office_extension_checklist_count": len(starter_checklist),
        "office_extension_phase_count": len(starter_phases),
        "office_extension_doc": office_extension_story.get("starter_checklist_doc", ""),
        "office_extension_candidate_count": len(future_candidates),
        "office_extension_backlog_count": len(future_backlog),
        "office_launch_public_ready_count": launch_matrix_summary.get("public_ready_count", 0),
        "office_launch_office_count": launch_matrix_summary.get("office_count", 0),
        "office_launch_primary_allowed_count": launch_matrix_summary.get("primary_allowed_count", 0),
        "office_launch_legacy_count": launch_matrix_summary.get("legacy_count", 0),
        "public_deployment_mode": public_deployment.get("mode", ""),
        "static_export_command": static_export.get("command", ""),
        "static_export_entrypoint": static_export.get("entrypoint", ""),
        "static_export_backend_free": static_export.get("requires_backend") is False,
    }


def verify_public_demo_mode() -> dict[str, Any]:
    client = TestClient(app)
    demos: dict[str, Any] = {}
    all_links: list[str] = []
    errors: list[str] = []
    showcase_manifest = _verify_showcase_manifest(client, errors)
    inventory_response = client.get("/api/demo/comic-production/handoff-inventory")
    inventory_payload = inventory_response.json() if inventory_response.status_code == 200 else {}
    if inventory_response.status_code != 200:
        errors.append(f"comic handoff inventory endpoint returned {inventory_response.status_code}")
    if inventory_payload.get("calls_real_models") is not False:
        errors.append("comic handoff inventory must not call real models")
    if inventory_payload.get("requires_api_key") is not False:
        errors.append("comic handoff inventory must not require API key")
    if inventory_payload.get("production_verified_count", 0) != 0:
        errors.append("fixed public inventory must not claim real production quality verification")
    inventory_items = inventory_payload.get("items") or []
    inventory_recovery_items = [
        item for item in inventory_items
        if (item.get("recommended_recovery") or {}).get("action")
    ]
    inventory_image_items = [
        item for item in inventory_items
        if isinstance(item.get("image_quality_summary"), dict)
    ]
    inventory_total_images = sum(int((item.get("image_quality_summary") or {}).get("total_images") or 0) for item in inventory_image_items)
    inventory_usable_images = sum(int((item.get("image_quality_summary") or {}).get("usable_images") or 0) for item in inventory_image_items)
    inventory_waste_images = sum(int((item.get("image_quality_summary") or {}).get("waste_or_rework_images") or 0) for item in inventory_image_items)
    inventory_waste_rate = (
        inventory_waste_images / inventory_total_images
        if inventory_total_images
        else 0
    )
    if inventory_payload.get("demo_only_count", 0) > 0 and not inventory_recovery_items:
        errors.append("comic handoff inventory demo-only items must expose recovery actions")
    if inventory_payload.get("demo_only_count", 0) > 0 and not inventory_image_items:
        errors.append("comic handoff inventory demo-only items must expose image quality summaries")
    for item in inventory_items:
        image_summary = item.get("image_quality_summary") or {}
        if not image_summary:
            errors.append(f"comic handoff inventory item missing image quality summary: {item.get('title') or item.get('quality_claim')}")
            continue
        for field in ("total_images", "usable_images", "waste_or_rework_images", "waste_or_rework_rate"):
            if field not in image_summary:
                errors.append(f"comic handoff inventory item image summary missing {field}: {item.get('title') or item.get('quality_claim')}")
        if "failed_image_ids" not in image_summary or not isinstance(image_summary.get("failed_image_ids"), list):
            errors.append(f"comic handoff inventory item image summary missing failed_image_ids: {item.get('title') or item.get('quality_claim')}")
        if "rework_action_summary" not in image_summary or not isinstance(image_summary.get("rework_action_summary"), list):
            errors.append(f"comic handoff inventory item image summary missing rework_action_summary: {item.get('title') or item.get('quality_claim')}")
    for item in inventory_recovery_items:
        recovery = item.get("recommended_recovery") or {}
        if not recovery.get("expected_stage") or not recovery.get("preserves") or not recovery.get("clears"):
            errors.append(f"comic handoff recovery item is incomplete: {item.get('title') or item.get('quality_claim')}")
    claim_response = client.get("/api/demo/comic-production/claim-report")
    claim_payload = claim_response.json() if claim_response.status_code == 200 else {}
    if claim_response.status_code != 200:
        errors.append(f"comic claim report endpoint returned {claim_response.status_code}")
    if claim_payload.get("calls_real_models") is not False:
        errors.append("comic claim report must not call real models")
    if claim_payload.get("requires_api_key") is not False:
        errors.append("comic claim report must not require API key")
    if claim_payload.get("claim_level") != "demo_structure_only":
        errors.append("fixed public claim report must remain demo_structure_only")
    if claim_payload.get("can_claim_real_quality") is not False:
        errors.append("fixed public claim report must not claim real production quality")
    real_model_evidence = claim_payload.get("real_model_evidence_requirements") or {}
    if real_model_evidence.get("status") != "evidence_missing":
        errors.append("fixed comic claim report must expose real_model_evidence_requirements.status=evidence_missing")
    if real_model_evidence.get("ready_for_real_quality_claim") is not False:
        errors.append("fixed comic claim report must expose ready_for_real_quality_claim=false")
    for marker in ("non_fixture_images", "provider_model_bound", "seven_dimension_scores"):
        if marker not in (real_model_evidence.get("missing_check_ids") or []):
            errors.append(f"fixed comic claim report real evidence is missing check id: {marker}")
    if len(real_model_evidence.get("checks") or []) < 6:
        errors.append("fixed comic claim report must include detailed real model evidence checks")
    claim_upgrade_checklist = claim_payload.get("claim_upgrade_checklist") or []
    if len(claim_upgrade_checklist) < 3:
        errors.append("fixed comic claim report must include a claim upgrade checklist")
    for item in claim_upgrade_checklist:
        if not item.get("id") or not item.get("status") or not item.get("required_evidence") or not item.get("why_it_matters"):
            errors.append(f"claim upgrade checklist item is incomplete: {item.get('id') or item.get('title')}")
    claim_upgrade_recovery = claim_payload.get("claim_upgrade_recovery") or {}
    if claim_upgrade_recovery.get("recovery_action") != "regenerate_images":
        errors.append("fixed comic claim report must include regenerate_images recovery action")
    if claim_upgrade_recovery.get("required") is not True:
        errors.append("fixed comic claim report must mark recovery as required")
    if len(claim_upgrade_recovery.get("steps") or []) < 3:
        errors.append("fixed comic claim report must include recovery steps")

    for office_id, meta in DEMO_ENDPOINTS.items():
        response = client.get(meta["endpoint"])
        available = response.status_code == 200
        payload = response.json() if available else {}
        downloads: list[dict[str, Any]] = []
        quality_benchmark: dict[str, Any] = {}
        honest_quality_gate: dict[str, Any] = {}
        if not available:
            errors.append(f"{office_id} demo endpoint returned {response.status_code}")

        if office_id == "comic_production" and available:
            quality_benchmark = payload.get("quality_benchmark") or {}
            honest_quality_gate = next(
                (
                    item
                    for item in payload.get("quality_gates") or []
                    if item.get("id") == "honest_quality_claim"
                ),
                {},
            )
            if quality_benchmark.get("status") != "demo_structure_verified":
                errors.append("comic production demo must claim demo_structure_verified")
            if quality_benchmark.get("package_quality_score") != 100:
                errors.append("comic production fixed demo must score 100/100 on the structural benchmark")
            if quality_benchmark.get("package_quality_ready") is not True:
                errors.append("comic production fixed demo must pass the structural package gate")
            if quality_benchmark.get("production_quality_verified") is not False:
                errors.append("comic production fixed demo must not claim real production image quality")
            if quality_benchmark.get("recommended_recovery"):
                errors.append("comic production passing demo must not expose a recovery action")
            prompt_quality = quality_benchmark.get("prompt_quality_summary") or {}
            if prompt_quality.get("status") != "ready":
                errors.append("comic production fixed demo must expose ready prompt quality")
            if prompt_quality.get("asset_prompt_count") != prompt_quality.get("clean_asset_prompt_count"):
                errors.append("comic production fixed demo must expose all asset prompts as clean")
            if prompt_quality.get("shot_prompt_count") != prompt_quality.get("director_prompt_count"):
                errors.append("comic production fixed demo must expose all director prompts as ready")
            if prompt_quality.get("issue_count") != 0:
                errors.append("comic production fixed demo must expose zero prompt quality issues")
            if honest_quality_gate.get("status") != "passed":
                errors.append("comic production demo honest quality gate must pass")

        for item in _download_items(payload):
            file_response = client.get(item["uri"])
            record = {
                "title": item["title"],
                "uri": item["uri"],
                "status_code": file_response.status_code,
                "bytes": len(file_response.content or b""),
                "content_type": file_response.headers.get("content-type", ""),
            }
            downloads.append(record)
            if record["status_code"] != 200:
                errors.append(f"{office_id} download failed: {item['uri']} -> {record['status_code']}")
            if record["bytes"] <= 20:
                errors.append(f"{office_id} download too small: {item['uri']} -> {record['bytes']} bytes")

        if len(downloads) < 2:
            errors.append(f"{office_id} exposes fewer than 2 downloadable demo files")

        gate_links = _collect_launch_gate_links(client, meta["launch_gate_endpoint"])
        all_links.extend(gate_links)
        if not gate_links:
            errors.append(f"{office_id} launch gates do not expose evidence links")

        demos[office_id] = {
            "name": meta["name"],
            "endpoint": meta["endpoint"],
            "available": available,
            "requires_api_key": False,
            "calls_real_models": False,
            "read_only": True,
            "downloads": downloads,
            "launch_gate_links": gate_links,
            "quality_benchmark": quality_benchmark,
            "honest_quality_gate": honest_quality_gate,
        }

    required_links = {
        "/api/demo/comic-production/files/word_canvas.docx",
        "/api/demo/comic-production/files/handoff_manifest.json",
        "/api/demo/research/files/report.md",
        "/api/demo/research/files/evidence_manifest.json",
    }
    missing_links = sorted(required_links.difference(all_links))
    for uri in missing_links:
        errors.append(f"launch gate evidence missing {uri}")

    return {
        "status": "passed" if not errors else "failed",
        "mode": "public_no_key_demo",
        "summary": "公开展示清单、演示端点、样例下载、真实生产声明和上线门禁链接可用" if not errors else "公开演示验证发现问题",
        "showcase_manifest": showcase_manifest,
        "comic_handoff_inventory": {
            "status_code": inventory_response.status_code,
            "status": inventory_payload.get("status", ""),
            "manifest_count": inventory_payload.get("manifest_count", 0),
            "production_verified_count": inventory_payload.get("production_verified_count", 0),
            "demo_only_count": inventory_payload.get("demo_only_count", 0),
            "needs_review_count": inventory_payload.get("needs_review_count", 0),
            "safe_public_claim": inventory_payload.get("safe_public_claim", ""),
            "recovery_item_count": len(inventory_recovery_items),
            "recovery_actions": sorted({
                str((item.get("recommended_recovery") or {}).get("action") or "")
                for item in inventory_recovery_items
                if (item.get("recommended_recovery") or {}).get("action")
            }),
            "recovery_stage_count": len({
                str((item.get("recommended_recovery") or {}).get("expected_stage") or "")
                for item in inventory_recovery_items
                if (item.get("recommended_recovery") or {}).get("expected_stage")
            }),
            "image_quality_item_count": len(inventory_image_items),
            "total_images": inventory_total_images,
            "usable_images": inventory_usable_images,
            "waste_or_rework_images": inventory_waste_images,
            "waste_or_rework_rate": inventory_waste_rate,
        },
        "comic_real_production_claim": {
            "status_code": claim_response.status_code,
            "claim_level": claim_payload.get("claim_level", ""),
            "quality_claim": claim_payload.get("quality_claim", ""),
            "can_claim_real_quality": claim_payload.get("can_claim_real_quality"),
            "downstream_status": claim_payload.get("downstream_status", ""),
            "upgrade_checklist_count": len(claim_upgrade_checklist),
            "recovery_action": claim_upgrade_recovery.get("recovery_action", ""),
            "recovery_step_count": len(claim_upgrade_recovery.get("steps") or []),
        },
        "demos": demos,
        "launch_gate_links": sorted(set(all_links)),
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    manifest = payload.get("showcase_manifest") or {}
    inventory = payload.get("comic_handoff_inventory") or {}
    claim = payload.get("comic_real_production_claim") or {}
    lines = [
        "# 公开演示模式验证",
        "",
        f"状态：{payload['status']}",
        f"模式：{payload['mode']}",
        f"说明：{payload['summary']}",
        "",
        "本验证只检查无 Key 演示端点、公开展示清单、样例交付物下载和上线门禁链接，不调用真实模型。",
        "",
        "## 公开展示清单",
        "",
        f"- 入口：`/api/demo/public-showcase`",
        f"- HTTP：{manifest.get('status_code')}",
        f"- 模式：{manifest.get('mode')}",
        f"- 访客路径：{manifest.get('audience_path_count')} 条",
        f"- 推荐演示：{manifest.get('featured_demo_count')} 个",
        f"- 可公开作品集展示：{manifest.get('safe_for_public_portfolio')}",
        f"- 作品集样例交付物：{manifest.get('portfolio_deliverable_count')} 个",
        f"- 带阅读说明的样例交付物：{manifest.get('deliverables_with_reader_guidance')} 个",
        f"- 最快验收路线：{manifest.get('fast_review_count')} 步，其中 {manifest.get('fast_review_ready_count')} 步可复核",
        f"- 交付物阅读顺序：{manifest.get('reading_guide_count')} 步，其中 {manifest.get('reading_guide_ready_count')} 步可复核",
        f"- 下游生产 quick-start：{manifest.get('downstream_quick_start_count')} 步，其中 {manifest.get('downstream_quick_start_ready_count')} 步可执行",
        f"- 面试演示脚本：{manifest.get('interview_script_count')} 步，其中 {manifest.get('interview_script_ready_count')} 步可复用",
        f"- 复现与验收清单：{manifest.get('reproducibility_count')} 步，其中 {manifest.get('reproducibility_ready_count')} 步可执行",
        f"- 发布状态铭牌：{manifest.get('release_badge_status')}，信号 {manifest.get('release_badge_signal_count')} 条，真实画质声明 {manifest.get('release_badge_claim_real_quality')}",
        f"- 漫剧交付盘点：{inventory.get('manifest_count')} 份，真实质量通过 {inventory.get('production_verified_count')} 份，结构样例 {inventory.get('demo_only_count')} 份",
        f"- 漫剧交付恢复动作：{inventory.get('recovery_item_count')} 份可恢复，动作 {', '.join(inventory.get('recovery_actions') or []) or '无'}，阶段 {inventory.get('recovery_stage_count')}",
        f"- 漫剧公开质量声明：{inventory.get('safe_public_claim')}",
        f"- 真实证据升级路径：action={manifest.get('quality_upgrade_recovery_action')} / steps={manifest.get('quality_upgrade_step_count')}",
        f"- 个人网站接入：source={manifest.get('portfolio_integration_source_dir')} / options={manifest.get('portfolio_integration_option_count')}",
        f"- New office extension: checklist={manifest.get('office_extension_checklist_count')} / phases={manifest.get('office_extension_phase_count')} / doc={manifest.get('office_extension_doc')}",
        f"- Future office candidates: {manifest.get('office_extension_candidate_count')} / backlog={manifest.get('office_extension_backlog_count')}",
        f"- Office launch matrix: public_ready={manifest.get('office_launch_public_ready_count')}/{manifest.get('office_launch_office_count')} / primary={manifest.get('office_launch_primary_allowed_count')} / legacy={manifest.get('office_launch_legacy_count')}",
        f"- 公开部署模式：{manifest.get('public_deployment_mode')}",
        "",
    ]
    lines.insert(
        -1,
        f"- AI comic claim report: {claim.get('claim_level')} / real_quality={claim.get('can_claim_real_quality')} / downstream={claim.get('downstream_status')} / upgrade_checklist={claim.get('upgrade_checklist_count')} / recovery={claim.get('recovery_action')} / recovery_steps={claim.get('recovery_step_count')}",
    )
    for demo in payload["demos"].values():
        lines.extend([
            f"## {demo['name']}",
            "",
            f"- 入口：`{demo['endpoint']}`",
            f"- 可访问：{demo['available']}",
            f"- 不消耗 Key：{not demo['requires_api_key']}",
            f"- 不调用真实模型：{not demo['calls_real_models']}",
            f"- 只读演示：{demo['read_only']}",
            "- 下载链接：",
        ])
        for item in demo["downloads"]:
            lines.append(
                f"  - `{item['uri']}`：HTTP {item['status_code']}，{item['bytes']} bytes"
            )
        benchmark = demo.get("quality_benchmark") or {}
        if benchmark:
            lines.extend([
                f"- 固定样例质量基准：{benchmark.get('package_quality_score', 0)}/100",
                f"- 质量声明：`{benchmark.get('status', '')}`",
                f"- 已验证真实模型画质：{benchmark.get('production_quality_verified')}",
            ])
            prompt_quality = benchmark.get("prompt_quality_summary") or {}
            if prompt_quality:
                lines.append(
                    "- Prompt quality: "
                    f"{prompt_quality.get('status')} / "
                    f"assets={prompt_quality.get('clean_asset_prompt_count')}/{prompt_quality.get('asset_prompt_count')} / "
                    f"directors={prompt_quality.get('director_prompt_count')}/{prompt_quality.get('shot_prompt_count')} / "
                    f"issues={prompt_quality.get('issue_count')}"
                )
        lines.append("")
    if payload.get("errors"):
        lines.append("## 问题")
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    payload = verify_public_demo_mode()
    if args.format == "markdown":
        print(format_markdown(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
