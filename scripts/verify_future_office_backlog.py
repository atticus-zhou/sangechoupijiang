"""Verify that future office candidates stay honestly blocked until they have evidence."""

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

from src.offices import audit_office_extension_governance


EXPECTED_CANDIDATES = {
    "short_video_ads",
    "ecommerce_selection",
    "story_ip",
    "technical_project",
}
EXPECTED_BACKLOG = {
    "future_schema_validators",
    "future_recovery_events",
}
REQUIRED_PUBLIC_BLOCKERS = {
    "sample_delivery",
    "schema_gate",
    "public_claim_report",
}
PLATFORM_BACKLOG_BY_REQUIREMENT = {
    "schema_gate": "future_schema_validators",
    "failure_recovery": "future_recovery_events",
    "recovery_actions": "future_recovery_events",
    "history_trace": "future_recovery_events",
}


def _candidate_report(candidate: dict[str, Any], backlog_ids: set[str]) -> dict[str, Any]:
    required = [str(item) for item in candidate.get("required_before_public") or [] if str(item).strip()]
    required_set = set(required)
    blocking_backlog = sorted({
        backlog_id
        for requirement, backlog_id in PLATFORM_BACKLOG_BY_REQUIREMENT.items()
        if requirement in required_set and backlog_id in backlog_ids
    })
    missing_core_blockers = sorted(REQUIRED_PUBLIC_BLOCKERS - required_set)
    errors: list[str] = []
    if not candidate.get("id"):
        errors.append("candidate is missing id")
    if not candidate.get("name"):
        errors.append("candidate is missing name")
    if not candidate.get("user_job"):
        errors.append("candidate is missing user_job")
    if not candidate.get("not_ready_reason"):
        errors.append("candidate is missing not_ready_reason")
    if len(required) < 5:
        errors.append("candidate must list at least five public-readiness requirements")
    if missing_core_blockers:
        errors.append(f"candidate is missing core blockers: {', '.join(missing_core_blockers)}")
    if "schema_gate" in required_set and "future_schema_validators" not in blocking_backlog:
        errors.append("schema_gate requirement must map to future_schema_validators")
    if required_set & {"failure_recovery", "recovery_actions", "history_trace"} and "future_recovery_events" not in blocking_backlog:
        errors.append("recovery or trace requirement must map to future_recovery_events")
    return {
        "id": candidate.get("id", ""),
        "name": candidate.get("name", ""),
        "user_job": candidate.get("user_job", ""),
        "not_ready_reason": candidate.get("not_ready_reason", ""),
        "required_before_public": required,
        "blocking_backlog_ids": blocking_backlog,
        "missing_core_blockers": missing_core_blockers,
        "status": "blocked_until_evidence" if not errors else "needs_backlog_detail",
        "errors": errors,
    }


def verify_future_office_backlog() -> dict[str, Any]:
    audit = audit_office_extension_governance()
    blueprint = audit.get("extension_blueprint") or {}
    candidates = blueprint.get("future_office_candidates") or []
    backlog = blueprint.get("future_platform_backlog") or []
    launch_matrix = audit.get("launch_matrix") or []

    candidate_ids = {str(item.get("id") or "") for item in candidates}
    backlog_ids = {str(item.get("id") or "") for item in backlog}
    launch_by_id = {str(item.get("office_id") or ""): item for item in launch_matrix}
    reports = [_candidate_report(candidate, backlog_ids) for candidate in candidates]

    errors: list[str] = []
    missing_candidates = sorted(EXPECTED_CANDIDATES - candidate_ids)
    missing_backlog = sorted(EXPECTED_BACKLOG - backlog_ids)
    if missing_candidates:
        errors.append(f"missing future office candidates: {', '.join(missing_candidates)}")
    if missing_backlog:
        errors.append(f"missing future platform backlog items: {', '.join(missing_backlog)}")
    for report in reports:
        errors.extend(f"{report['id']}: {error}" for error in report["errors"])
        launch = launch_by_id.get(report["id"])
        if launch and (launch.get("can_show_publicly") or launch.get("primary_allowed")):
            errors.append(f"{report['id']} is still a future candidate but appears publicly launchable")
    for item in backlog:
        backlog_id = str(item.get("id") or "")
        if not item.get("description") or not item.get("evidence_required"):
            errors.append(f"{backlog_id or 'unknown_backlog'} is missing description or evidence_required")

    blocked_count = sum(1 for item in reports if item["status"] == "blocked_until_evidence")
    return {
        "status": "passed" if not errors else "failed",
        "mode": "future_office_backlog",
        "summary": (
            "Future office candidates are documented as blocked until they add office-specific schema, recovery, demo, claim, and release evidence."
            if not errors
            else "Future office backlog has gaps."
        ),
        "candidate_count": len(candidates),
        "blocked_candidate_count": blocked_count,
        "candidate_ids": sorted(candidate_id for candidate_id in candidate_ids if candidate_id),
        "backlog_count": len(backlog),
        "backlog_ids": sorted(backlog_id for backlog_id in backlog_ids if backlog_id),
        "reports": reports,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Future Office Backlog",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Summary: {payload.get('summary')}",
        "",
        f"- Candidates: {payload.get('blocked_candidate_count')}/{payload.get('candidate_count')} blocked until evidence",
        f"- Platform backlog: {payload.get('backlog_count')} items ({', '.join(payload.get('backlog_ids') or [])})",
        "",
        "| Candidate | Status | Required before public | Platform blockers |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload.get("reports") or []:
        lines.append(
            "| {id} | {status} | {required} | {backlog} |".format(
                id=item.get("id", ""),
                status=item.get("status", ""),
                required=", ".join(item.get("required_before_public") or []),
                backlog=", ".join(item.get("blocking_backlog_ids") or []) or "-",
            )
        )
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()
    payload = verify_future_office_backlog()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
