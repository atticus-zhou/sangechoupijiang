"""Verify the no-key real-quality upgrade plan for AI comic production.

The plan is not a model runner. It proves that a user can see the exact
preflight, recovery, evidence, and verification steps required before a demo
structure package may be upgraded to a real-quality public claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.web.app import app


def verify_upgrade_plan() -> dict[str, Any]:
    from fastapi.testclient import TestClient

    errors: list[str] = []
    client = TestClient(app)
    response = client.get("/api/demo/comic-production/real-quality-upgrade-plan")
    payload = response.json() if response.status_code == 200 else {}

    if response.status_code != 200:
        errors.append(f"upgrade plan endpoint returned {response.status_code}")
    if payload.get("mode") != "no_key_real_quality_upgrade_plan":
        errors.append("upgrade plan must stay in no_key_real_quality_upgrade_plan mode")
    if payload.get("requires_api_key") is not False:
        errors.append("upgrade plan must not require API key")
    if payload.get("calls_real_models") is not False:
        errors.append("upgrade plan must not call real models")
    if payload.get("writes_workspace") is not False:
        errors.append("upgrade plan must not write workspace data")
    if payload.get("current_claim_level") != "demo_structure_only":
        errors.append("fixed demo should currently be demo_structure_only")
    if payload.get("target_claim_level") != "real_quality_verified":
        errors.append("upgrade target must be real_quality_verified")
    if payload.get("handoff_allowed_now") is not False:
        errors.append("demo structure package must not be marked handoff-ready")
    if payload.get("can_claim_real_quality_now") is not False:
        errors.append("demo structure package must not claim real quality")
    if payload.get("upgrade_status") != "blocked_until_real_model_evidence":
        errors.append("demo upgrade status must stay blocked until real model evidence exists")

    model_departments = payload.get("model_preflight_departments") or []
    department_ids = {item.get("department_id") for item in model_departments}
    for required in ("gongbu", "xingbu", "bingbu"):
        if required not in department_ids:
            errors.append(f"upgrade plan missing model preflight department: {required}")
    for item in model_departments:
        if not item.get("required_capability") or not item.get("why"):
            errors.append(f"model preflight item is incomplete: {item.get('department_id')}")

    steps = payload.get("operator_steps") or []
    phases = [item.get("phase") for item in steps]
    expected_phases = ["preflight", "recover_images", "visual_review", "rebuild_delivery", "release_claim"]
    if phases != expected_phases:
        errors.append("upgrade plan operator steps must follow preflight/recover/review/rebuild/release order")
    for item in steps:
        if not item.get("owner") or not item.get("action") or not item.get("done_when"):
            errors.append(f"operator step is incomplete: {item.get('phase') or item.get('order')}")

    evidence = payload.get("evidence_contract") or {}
    if evidence.get("ready_for_real_quality_claim") is not False:
        errors.append("fixed demo evidence contract must not be ready for real quality claim")
    for marker in ("non_fixture_images", "provider_model_bound"):
        if marker not in (evidence.get("missing_check_ids") or []):
            errors.append(f"evidence contract missing blocking marker: {marker}")
    if int(evidence.get("seven_dimension_scored_reviews") or 0) < 1:
        errors.append("upgrade plan should show seven-dimension review evidence requirement")

    checklist = payload.get("claim_upgrade_checklist") or []
    checklist_ids = {item.get("id") for item in checklist}
    for item_id in ("run_real_models", "visual_review", "stored_benchmark", "real_model_evidence_contract"):
        if item_id not in checklist_ids:
            errors.append(f"upgrade checklist missing item: {item_id}")
    if payload.get("recovery_action") != "regenerate_images":
        errors.append("upgrade recovery action must be regenerate_images")
    if "prompt_package" not in (payload.get("preserves") or []):
        errors.append("upgrade plan must preserve prompt_package")
    if "visual_review" not in (payload.get("rebuilds") or []):
        errors.append("upgrade plan must rebuild visual_review")
    commands = "\n".join(payload.get("verification_commands") or [])
    for command in (
        "verify_comic_real_production_claim.py",
        "verify_comic_v2_production_benchmark.py",
        "verify_comic_v2_downstream_handoff.py",
        "check_no_secrets.py",
    ):
        if command not in commands:
            errors.append(f"upgrade plan missing verification command: {command}")
    boundary = str(payload.get("public_boundary") or "")
    for marker in ("不读取 API Key", "不调用模型", "不写工作区"):
        if marker not in boundary:
            errors.append(f"upgrade plan public boundary missing marker: {marker}")

    ordered_departments = [
        item
        for item in ("gongbu", "xingbu", "bingbu")
        if item in department_ids
    ]

    return {
        "status": "passed" if not errors else "failed",
        "mode": "comic_real_quality_upgrade_plan",
        "summary": (
            "AI comic demo exposes a no-key, human-operable path from demo_structure_only to real_quality_verified."
            if not errors
            else "AI comic real-quality upgrade plan has gaps."
        ),
        "status_code": response.status_code,
        "current_claim_level": payload.get("current_claim_level", ""),
        "target_claim_level": payload.get("target_claim_level", ""),
        "upgrade_status": payload.get("upgrade_status", ""),
        "handoff_allowed_now": bool(payload.get("handoff_allowed_now")),
        "can_claim_real_quality_now": bool(payload.get("can_claim_real_quality_now")),
        "model_preflight_departments": ordered_departments,
        "operator_step_count": len(steps),
        "operator_phases": phases,
        "evidence_missing_checks": evidence.get("missing_check_ids") or [],
        "seven_dimension_scored_reviews": int(evidence.get("seven_dimension_scored_reviews") or 0),
        "checklist_ids": sorted(checklist_ids),
        "recovery_action": payload.get("recovery_action", ""),
        "verification_command_count": len(payload.get("verification_commands") or []),
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# AI Comic Real Quality Upgrade Plan",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Summary: {payload.get('summary')}",
        "",
        f"- Current claim: `{payload.get('current_claim_level')}`",
        f"- Target claim: `{payload.get('target_claim_level')}`",
        f"- Upgrade status: `{payload.get('upgrade_status')}`",
        f"- Handoff allowed now: `{payload.get('handoff_allowed_now')}`",
        f"- Can claim real quality now: `{payload.get('can_claim_real_quality_now')}`",
        f"- Model preflight departments: `{', '.join(payload.get('model_preflight_departments') or [])}`",
        f"- Operator steps: `{payload.get('operator_step_count')}` ({', '.join(payload.get('operator_phases') or [])})",
        f"- Evidence missing checks: `{', '.join(payload.get('evidence_missing_checks') or [])}`",
        f"- Seven-dimension reviews: `{payload.get('seven_dimension_scored_reviews')}`",
        f"- Recovery action: `{payload.get('recovery_action')}`",
        f"- Verification commands: `{payload.get('verification_command_count')}`",
    ]
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()
    payload = verify_upgrade_plan()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
