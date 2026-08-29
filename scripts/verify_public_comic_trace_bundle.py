"""Verify the public no-key comic trace bundle."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from src.web.app import app


TRACE_URI = "/api/demo/comic-production/files/trace.json"
SECRET_PATTERNS = {
    "openai_style_secret": re.compile(r"sk-[A-Za-z0-9_-]{16,}", re.I),
    "long_api_key_assignment": re.compile(r"api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_-]{12,}", re.I),
    "windows_local_path": re.compile(r"[A-Z]:\\\\", re.I),
    "cookie_header": re.compile(r"\bCookie\s*[:=]", re.I),
}


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _collect_trace_errors(trace: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    text = _json_text(trace)
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            errors.append(f"trace bundle leaks forbidden marker: {label}")

    if trace.get("mode") != "no_key_demo_comic_v2_trace":
        errors.append("trace bundle has an unexpected mode")
    for flag in ("requires_api_key", "calls_real_models", "writes_workspace"):
        if trace.get(flag) is not False:
            errors.append(f"trace bundle must keep {flag}=False")

    story = trace.get("story") or {}
    style = trace.get("style") or {}
    assets = trace.get("assets") or []
    images = trace.get("images") or []
    shots = trace.get("shots") or []
    if not story.get("story_id") or not story.get("title"):
        errors.append("trace bundle must expose story_id and title")
    if not style.get("style_id"):
        errors.append("trace bundle must expose style_id")
    if len(assets) < 3:
        errors.append("trace bundle must include character, prop, and scene assets")
    if len(images) < 7:
        errors.append("trace bundle must include the public demo image records")
    if len(shots) < 2:
        errors.append("trace bundle must include shot records")

    asset_ids = {str(item.get("asset_id") or "") for item in assets}
    image_ids = {str(item.get("image_id") or "") for item in images}
    missing_image_assets = sorted({
        str(item.get("asset_id") or "")
        for item in images
        if item.get("asset_id") and str(item.get("asset_id") or "") not in asset_ids
    })
    if missing_image_assets:
        errors.append(f"image records reference missing assets: {', '.join(missing_image_assets)}")
    for shot in shots:
        shot_id = str(shot.get("shot_id") or "")
        for asset_id in shot.get("reference_asset_ids") or []:
            if str(asset_id) not in asset_ids:
                errors.append(f"shot {shot_id} references missing asset: {asset_id}")
        first_frame = shot.get("first_frame_reference_image") or {}
        first_frame_id = str(first_frame.get("image_id") or "")
        if first_frame_id and first_frame_id not in image_ids:
            errors.append(f"shot {shot_id} references missing first-frame image: {first_frame_id}")

    quality = trace.get("quality_benchmark") or {}
    if quality.get("status") != "demo_structure_verified":
        errors.append("trace quality benchmark must remain demo_structure_verified")
    if quality.get("production_quality_verified") is not False:
        errors.append("public trace must not claim production-quality visual evidence")
    if quality.get("visual_evidence_level") != "fixture_only":
        errors.append("public trace must keep visual_evidence_level=fixture_only")
    real_model_evidence = quality.get("real_model_evidence_requirements") or {}
    if real_model_evidence.get("status") != "evidence_missing":
        errors.append("public trace must expose real_model_evidence_requirements.status=evidence_missing")
    if real_model_evidence.get("ready_for_real_quality_claim") is not False:
        errors.append("public trace must expose ready_for_real_quality_claim=false")
    for marker in ("non_fixture_images", "provider_model_bound"):
        if marker not in (real_model_evidence.get("missing_check_ids") or []):
            errors.append(f"public trace real model evidence is missing check id: {marker}")
    if "seven_dimension_scores" in (real_model_evidence.get("missing_check_ids") or []):
        errors.append("public trace should not list seven_dimension_scores as missing after fixture QA is scored")
    if int(real_model_evidence.get("seven_dimension_scored_reviews") or 0) <= 0:
        errors.append("public trace should expose scored fixture visual reviews")
    if len(real_model_evidence.get("checks") or []) < 6:
        errors.append("public trace real model evidence must include detailed checks")

    image_evidence = trace.get("image_production_evidence") or {}
    if image_evidence.get("evidence_level") != "fixture_only":
        errors.append("image production evidence must remain fixture_only for the public demo")
    if image_evidence.get("supports_real_quality_claim") is not False:
        errors.append("public fixture images must not support a real quality claim")
    if image_evidence.get("total_images") != len(images):
        errors.append("image production evidence total_images must match trace images")
    if not image_evidence.get("next_action"):
        errors.append("image production evidence must include a next action")
    by_asset_type = image_evidence.get("by_asset_type") or {}
    for asset_type in ("character", "prop", "scene"):
        bucket = by_asset_type.get(asset_type) or {}
        if int(bucket.get("total") or 0) <= 0:
            errors.append(f"image production evidence must expose {asset_type} quality totals")
        if "waste_or_rework" not in bucket:
            errors.append(f"image production evidence must expose {asset_type} waste_or_rework")

    if trace.get("claim_level") != "demo_structure_only":
        errors.append("trace claim_level must remain demo_structure_only")
    handoff_decision = trace.get("downstream_handoff_decision") or {}
    if handoff_decision.get("status") != "structure_demo_only":
        errors.append("trace must expose downstream_handoff_decision.status=structure_demo_only")
    if handoff_decision.get("handoff_allowed") is not False:
        errors.append("trace must not allow downstream handoff for fixture demos")
    if "不能交给下游" not in str(handoff_decision.get("decision") or ""):
        errors.append("trace downstream handoff decision must explain the demo-only boundary")
    if "真实模型生成的非 fixture 图片" not in (handoff_decision.get("missing_before_handoff") or []):
        errors.append("trace downstream decision must list missing non-fixture images")
    if "regenerate_images" not in "\n".join(str(item) for item in (handoff_decision.get("required_actions") or [])):
        errors.append("trace downstream decision must point to regenerate_images")
    checklist = trace.get("claim_upgrade_checklist") or []
    if len(checklist) < 3:
        errors.append("trace bundle must include the claim upgrade checklist")
    for item in checklist:
        if not item.get("id") or not item.get("required_evidence") or not item.get("why_it_matters"):
            errors.append(f"claim upgrade checklist item is incomplete: {item.get('id') or item.get('title')}")

    reproducibility = trace.get("reproducibility") or {}
    commands = "\n".join(str(item) for item in reproducibility.get("verification_commands") or [])
    for marker in (
        "verify_public_demo_mode.py",
        "verify_comic_v2_downstream_handoff.py",
        "verify_comic_real_production_claim.py",
    ):
        if marker not in commands:
            errors.append(f"trace reproducibility is missing command: {marker}")
    if "真实画质" not in str(reproducibility.get("public_claim_boundary") or ""):
        errors.append("trace reproducibility must state the public real-quality boundary")

    return errors


def verify_public_comic_trace_bundle() -> dict[str, Any]:
    client = TestClient(app)
    response = client.get(TRACE_URI)
    trace = response.json() if response.status_code == 200 else {}
    errors = []
    if response.status_code != 200:
        errors.append(f"{TRACE_URI} returned HTTP {response.status_code}")
    elif not isinstance(trace, dict):
        errors.append("trace endpoint did not return a JSON object")
        trace = {}
    else:
        errors.extend(_collect_trace_errors(trace))

    image_evidence = trace.get("image_production_evidence") or {}
    quality = trace.get("quality_benchmark") or {}
    real_model_evidence = quality.get("real_model_evidence_requirements") or {}
    handoff_decision = trace.get("downstream_handoff_decision") or {}
    return {
        "status": "passed" if not errors else "failed",
        "mode": "public_comic_trace_bundle",
        "uri": TRACE_URI,
        "summary": (
            "Public comic trace bundle is downloadable, safe, traceable, and honest about fixture-only image evidence."
            if not errors
            else "Public comic trace bundle has gaps."
        ),
        "requires_api_key": trace.get("requires_api_key") if trace else None,
        "calls_real_models": trace.get("calls_real_models") if trace else None,
        "writes_workspace": trace.get("writes_workspace") if trace else None,
        "story_id": (trace.get("story") or {}).get("story_id", "") if trace else "",
        "style_id": (trace.get("style") or {}).get("style_id", "") if trace else "",
        "asset_count": len(trace.get("assets") or []) if trace else 0,
        "image_count": len(trace.get("images") or []) if trace else 0,
        "shot_count": len(trace.get("shots") or []) if trace else 0,
        "claim_level": trace.get("claim_level", "") if trace else "",
        "quality_status": quality.get("status", ""),
        "visual_evidence_level": quality.get("visual_evidence_level", ""),
        "production_quality_verified": quality.get("production_quality_verified"),
        "image_evidence_level": image_evidence.get("evidence_level", ""),
        "supports_real_quality_claim": image_evidence.get("supports_real_quality_claim"),
        "asset_type_quality": image_evidence.get("by_asset_type") or {},
        "real_model_evidence_status": real_model_evidence.get("status", ""),
        "real_model_evidence_ready": real_model_evidence.get("ready_for_real_quality_claim"),
        "real_model_evidence_missing_checks": list(real_model_evidence.get("missing_check_ids") or []),
        "downstream_handoff_status": handoff_decision.get("status", ""),
        "downstream_handoff_allowed": handoff_decision.get("handoff_allowed"),
        "upgrade_checklist_count": len(trace.get("claim_upgrade_checklist") or []) if trace else 0,
        "reproducibility_command_count": len((trace.get("reproducibility") or {}).get("verification_commands") or []) if trace else 0,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Public Comic Trace Bundle",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"URI: `{payload.get('uri')}`",
        f"Summary: {payload.get('summary')}",
        "",
        f"- API Key required: {payload.get('requires_api_key')}",
        f"- Calls real models: {payload.get('calls_real_models')}",
        f"- Writes workspace: {payload.get('writes_workspace')}",
        f"- Story/style: {payload.get('story_id')} / {payload.get('style_id')}",
        f"- Assets/images/shots: {payload.get('asset_count')} / {payload.get('image_count')} / {payload.get('shot_count')}",
        f"- Claim level: {payload.get('claim_level')}",
        f"- Quality: {payload.get('quality_status')} / visual={payload.get('visual_evidence_level')} / real={payload.get('production_quality_verified')}",
        f"- Image evidence: {payload.get('image_evidence_level')} / supports_real_quality={payload.get('supports_real_quality_claim')}",
        f"- Asset type quality: {_format_asset_type_quality(payload.get('asset_type_quality') or {})}",
        f"- Real model evidence: {payload.get('real_model_evidence_status')} / ready={payload.get('real_model_evidence_ready')}",
        f"- Missing real model checks: {', '.join(payload.get('real_model_evidence_missing_checks') or [])}",
        f"- Downstream handoff: {payload.get('downstream_handoff_status')} / allowed={payload.get('downstream_handoff_allowed')}",
        f"- Upgrade checklist: {payload.get('upgrade_checklist_count')} items",
        f"- Reproducibility commands: {payload.get('reproducibility_command_count')}",
    ]
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    return "\n".join(lines) + "\n"


def _format_asset_type_quality(by_asset_type: dict[str, Any]) -> str:
    parts = []
    for asset_type in ("character", "prop", "scene", "shot_reference", "unclassified"):
        item = by_asset_type.get(asset_type) or {}
        total = int(item.get("total") or 0)
        if total <= 0:
            continue
        parts.append(
            f"{asset_type}={item.get('passed', 0)}/{total} passed, "
            f"{item.get('waste_or_rework', 0)} rework"
        )
    return "; ".join(parts) or "missing"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()
    payload = verify_public_comic_trace_bundle()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
