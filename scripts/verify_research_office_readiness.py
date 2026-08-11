"""Verify research-office demo and artifact readiness without real model calls."""

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

from src.research_artifacts import build_research_artifacts
from src.research_quality import assess_research_package
from src.web.app import app


REQUIRED_RESEARCH_ARTIFACTS = {
    "report",
    "standard_report",
    "briefing",
    "source_list",
    "data_table",
    "competitor_table",
    "review_pain_points",
    "opportunity_map",
    "chart_plan",
    "screenshot_plan",
    "evidence_gap_cards",
}

SCHEMA_GATED_ARTIFACTS = {
    "standard_report": "research_standard_report",
    "source_list": "research_source_list",
    "data_table": "research_data_table",
    "competitor_table": "research_competitor_table",
}


def _load_fixture() -> dict[str, Any]:
    fixture_path = REPO_ROOT / "tests" / "fixtures" / "research_sample.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _verify_artifact_package(errors: list[str]) -> dict[str, Any]:
    result = _load_fixture()
    artifacts = build_research_artifacts("demo_research", result)
    by_type = {item.get("artifact_type"): item for item in artifacts}
    artifact_types = set(by_type)
    missing_artifacts = sorted(REQUIRED_RESEARCH_ARTIFACTS - artifact_types)
    if missing_artifacts:
        errors.append("research package missing artifacts: " + ", ".join(missing_artifacts))

    schema_gates: dict[str, Any] = {}
    for artifact_type, schema_id in SCHEMA_GATED_ARTIFACTS.items():
        artifact = by_type.get(artifact_type) or {}
        schema_gate = (artifact.get("metadata") or {}).get("schema_gate") or {}
        schema_gates[artifact_type] = schema_gate
        if schema_gate.get("schema_id") != schema_id:
            errors.append(f"{artifact_type} did not record schema gate {schema_id}")
        if schema_gate.get("status") != "passed":
            errors.append(f"{artifact_type} schema gate did not pass")

    quality = assess_research_package(artifacts)
    if quality.get("status") != "ready":
        errors.append(f"research quality status is {quality.get('status')}")
    if quality.get("missing_artifacts"):
        errors.append("research quality has missing artifacts")

    screenshot_plan = by_type.get("screenshot_plan", {}).get("content", "")
    source_list = by_type.get("source_list", {}).get("content", "")
    data_table = by_type.get("data_table", {}).get("content", "")
    competitor_table = by_type.get("competitor_table", {}).get("content", "")
    evidence_gap_cards = by_type.get("evidence_gap_cards", {}).get("content", "")
    if "evidence_01.png" not in screenshot_plan:
        errors.append("screenshot plan must provide evidence file naming")
    if "补证卡" not in evidence_gap_cards or "负责人" not in evidence_gap_cards or "升级" not in evidence_gap_cards:
        errors.append("evidence gap cards must explain owner, missing evidence, and upgrade path")
    if "http" not in source_list and "local://" not in source_list:
        errors.append("source list must keep URL or pending local evidence references")
    if "|" not in data_table:
        errors.append("data table must be reusable markdown")
    if "|" not in competitor_table:
        errors.append("competitor table must be reusable markdown")

    return {
        "status": "passed" if not missing_artifacts and quality.get("status") == "ready" else "failed",
        "artifact_count": len(artifacts),
        "artifact_types": sorted(artifact_types),
        "missing_artifacts": missing_artifacts,
        "quality": quality,
        "schema_gates": schema_gates,
        "has_screenshot_plan": bool(screenshot_plan),
        "has_evidence_gap_cards": bool(evidence_gap_cards),
        "has_source_trace": "http" in source_list or "local://" in source_list,
        "has_data_table": "|" in data_table,
        "has_competitor_table": "|" in competitor_table,
    }


def _download_items(payload: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for item in payload.get("artifacts") or []:
        uri = str(item.get("uri") or "")
        if item.get("status") == "downloadable" and (
            uri.startswith("/api/demo/research/files/") or uri == "/api/demo/research/claim-report"
        ):
            items.append({"title": str(item.get("title") or uri), "uri": uri})
    return items


def _verify_demo_endpoint(errors: list[str]) -> dict[str, Any]:
    client = TestClient(app)
    response = client.get("/api/demo/research")
    if response.status_code != 200:
        errors.append(f"research demo returned {response.status_code}")
        return {"status": "failed", "status_code": response.status_code, "downloads": []}

    payload = response.json()
    if payload.get("mode") != "no_key_demo":
        errors.append("research demo must stay in no_key_demo mode")
    if payload.get("requires_api_key") is not False:
        errors.append("research demo must not require API key")
    if payload.get("calls_real_models") is not False:
        errors.append("research demo must not call real models")
    evidence_boundaries = payload.get("evidence_boundaries") or {}
    evidence_status_summary = payload.get("evidence_status_summary") or {}
    covered_in_demo = evidence_boundaries.get("covered_in_demo") or []
    requires_human_or_account = evidence_boundaries.get("requires_human_or_account") or []
    public_demo_boundary = str(evidence_boundaries.get("public_demo_boundary") or "")
    reading_guide = payload.get("deliverable_reading_guide") or []
    evidence_handoff = payload.get("evidence_handoff") or []
    evidence_gap_cards = payload.get("evidence_gap_cards") or []
    capture_playbook = payload.get("evidence_capture_playbook") or {}
    research_evidence_requirements = payload.get("research_evidence_requirements") or {}
    capture_steps = capture_playbook.get("steps") or []
    claim_response = client.get("/api/demo/research/claim-report")
    claim_report = claim_response.json() if claim_response.status_code == 200 else {}
    claim_capture_playbook = claim_report.get("evidence_capture_playbook") or {}
    claim_evidence_status_summary = claim_report.get("evidence_status_summary") or {}
    claim_research_evidence_requirements = claim_report.get("research_evidence_requirements") or {}
    if len(covered_in_demo) < 4:
        errors.append("research demo must describe which evidence is covered in the fixed sample")
    if len(requires_human_or_account) < 3:
        errors.append("research demo must describe account or human-gated evidence")
    if "不宣称全自动" not in public_demo_boundary:
        errors.append("research demo must state it does not claim full automation")
    if len(reading_guide) < 2:
        errors.append("research demo must provide a report/evidence reading guide")
    for item in reading_guide:
        if not str(item.get("uri") or "").startswith("/api/demo/research/files/"):
            errors.append(f"research reading guide item has invalid uri: {item.get('title') or item.get('uri')}")
        if not item.get("look_for") or not item.get("proves"):
            errors.append(f"research reading guide item missing look_for/proves: {item.get('title') or item.get('uri')}")
    if len(evidence_handoff) < 3:
        errors.append("research demo must expose at least 3 evidence handoff items")
    for item in evidence_handoff:
        if not item.get("owner") or not item.get("target_evidence") or not item.get("why_needed") or not item.get("upgrades"):
            errors.append(f"research evidence handoff item is incomplete: {item.get('title') or item.get('id')}")
        if not item.get("priority") or not item.get("suggested_file_name") or not item.get("acceptance"):
            errors.append(f"research evidence handoff item must include priority, suggested file name, and acceptance: {item.get('title') or item.get('id')}")
        if item.get("suggested_file_name") and "evidence_" not in str(item.get("suggested_file_name")):
            errors.append(f"research evidence handoff item must follow evidence file naming: {item.get('title') or item.get('id')}")
    if len(evidence_gap_cards) < 3:
        errors.append("research demo must expose at least 3 executable evidence gap cards")
    for item in evidence_gap_cards:
        if not item.get("owner") or not item.get("target_evidence") or not item.get("user_action") or not item.get("acceptance") or not item.get("upgrades"):
            errors.append(f"research evidence gap card is incomplete: {item.get('title') or item.get('id')}")
        if "evidence_" not in str(item.get("file_name") or ""):
            errors.append(f"research evidence gap card must define evidence file naming: {item.get('title') or item.get('id')}")
    if capture_playbook.get("status") != "human_account_required":
        errors.append("research demo must expose a human-account-required evidence capture playbook")
    if len(capture_steps) < 5:
        errors.append("research evidence capture playbook must provide at least 5 steps")
    if "evidence_" not in str(capture_playbook.get("file_naming_rule") or ""):
        errors.append("research evidence capture playbook must define evidence file naming")
    if "账号密码" not in "\n".join(capture_playbook.get("must_not_collect") or []):
        errors.append("research evidence capture playbook must forbid collecting account passwords")
    for item in capture_steps:
        if not item.get("owner") or not item.get("action") or not item.get("expected_artifact") or not item.get("acceptance"):
            errors.append(f"research evidence capture step is incomplete: {item.get('order') or item.get('action')}")
    if not any("verify_research_office_readiness.py" in str(command) for command in capture_playbook.get("after_capture_commands") or []):
        errors.append("research evidence capture playbook must include the readiness verifier command")
    status_counts = evidence_status_summary.get("counts") or {}
    if evidence_status_summary.get("claim_readiness") != "staged_only":
        errors.append("research demo evidence status must stay staged_only")
    if evidence_status_summary.get("can_claim_final_report") is not False:
        errors.append("research demo must not claim the sample supports a final verified report")
    if status_counts.get("placeholder_demo_source", 0) < 1:
        errors.append("research demo must identify placeholder demo sources")
    if status_counts.get("pending_account_or_manual_capture", 0) < 1:
        errors.append("research demo must identify pending account/manual evidence")
    if not evidence_status_summary.get("operator_message"):
        errors.append("research demo evidence status must include an operator-facing message")
    if research_evidence_requirements.get("status") != "staged_only":
        errors.append("research demo must expose research_evidence_requirements.status=staged_only")
    if research_evidence_requirements.get("ready_for_final_research_claim") is not False:
        errors.append("research demo must not claim final research evidence readiness")
    if research_evidence_requirements.get("can_claim_full_automation") is not False:
        errors.append("research demo evidence requirements must forbid full automation claims")
    for marker in ("pending_evidence_disclosed", "placeholder_sources_disclosed", "final_report_not_claimed"):
        if marker not in (research_evidence_requirements.get("blocking_check_ids") or []):
            errors.append(f"research evidence requirements missing blocking check id: {marker}")
    if len(research_evidence_requirements.get("checks") or []) < 6:
        errors.append("research evidence requirements must include detailed checks")
    if claim_response.status_code != 200:
        errors.append(f"research claim report returned {claim_response.status_code}")
    if claim_report.get("claim_level") != "staged_research_demo":
        errors.append("research claim report must stay at staged_research_demo")
    if claim_report.get("can_claim_full_automation") is not False:
        errors.append("research claim report must not claim full automation")
    if claim_report.get("requires_api_key") is not False or claim_report.get("calls_real_models") is not False:
        errors.append("research claim report must remain no-key and offline")
    if claim_evidence_status_summary.get("claim_readiness") != evidence_status_summary.get("claim_readiness"):
        errors.append("research claim report must repeat the evidence status summary")
    if claim_capture_playbook.get("status") != capture_playbook.get("status"):
        errors.append("research claim report must repeat the evidence capture playbook")
    if claim_research_evidence_requirements.get("status") != research_evidence_requirements.get("status"):
        errors.append("research claim report must repeat research evidence requirements")
    forbidden_claims = "\n".join(claim_report.get("forbidden_public_claims") or [])
    if "自动登录飞瓜" not in forbidden_claims or "会员级" not in forbidden_claims:
        errors.append("research claim report must forbid full platform automation claims")
    upgrade_checklist = claim_report.get("claim_upgrade_checklist") or []
    if len(upgrade_checklist) < 3:
        errors.append("research claim report must include a 3-step upgrade checklist")
    for item in upgrade_checklist:
        if not item.get("id") or not item.get("status") or not item.get("required_evidence") or not item.get("why_it_matters"):
            errors.append(f"research claim checklist item is incomplete: {item.get('id') or item.get('title')}")

    downloads = []
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
            errors.append(f"research demo download failed: {item['uri']}")
        if record["bytes"] <= 20:
            errors.append(f"research demo download too small: {item['uri']}")
        if item["uri"].endswith("/evidence_manifest.json") and record["status_code"] == 200:
            manifest = file_response.json()
            manifest_status = manifest.get("evidence_status_summary") or {}
            manifest_counts = manifest_status.get("counts") or {}
            if manifest_status.get("claim_readiness") != "staged_only":
                errors.append("research evidence manifest must record staged_only claim readiness")
            if manifest_status.get("can_claim_final_report") is not False:
                errors.append("research evidence manifest must not claim final-report readiness")
            if manifest_counts.get("placeholder_demo_source", 0) < 1:
                errors.append("research evidence manifest must count placeholder demo sources")
            if manifest_counts.get("pending_account_or_manual_capture", 0) < 1:
                errors.append("research evidence manifest must count pending capture evidence")
            if len(manifest.get("evidence_gap_cards") or []) < 3:
                errors.append("research evidence manifest must include executable evidence gap cards")

    required_downloads = {
        "/api/demo/research/files/report.md",
        "/api/demo/research/files/evidence_manifest.json",
        "/api/demo/research/claim-report",
    }
    present_downloads = {item["uri"] for item in downloads}
    missing_downloads = sorted(required_downloads - present_downloads)
    if missing_downloads:
        errors.append("research demo missing downloads: " + ", ".join(missing_downloads))

    return {
        "status": "passed" if response.status_code == 200 and not missing_downloads else "failed",
        "status_code": response.status_code,
        "mode": payload.get("mode", ""),
        "requires_api_key": bool(payload.get("requires_api_key")),
        "calls_real_models": bool(payload.get("calls_real_models")),
        "download_count": len(downloads),
        "downloads": downloads,
        "evidence_boundary_count": len(covered_in_demo),
        "human_or_account_boundary_count": len(requires_human_or_account),
        "public_demo_boundary": public_demo_boundary,
        "reading_guide_count": len(reading_guide),
        "reading_guide_ready_count": sum(
            1
            for item in reading_guide
            if str(item.get("uri") or "").startswith("/api/demo/research/files/")
            and item.get("look_for")
            and item.get("proves")
        ),
        "evidence_handoff_count": len(evidence_handoff),
        "evidence_handoff_ready_count": sum(
            1
            for item in evidence_handoff
            if item.get("owner") and item.get("target_evidence") and item.get("why_needed") and item.get("upgrades")
        ),
        "evidence_gap_card_count": len(evidence_gap_cards),
        "evidence_gap_card_ready_count": sum(
            1
            for item in evidence_gap_cards
            if item.get("owner")
            and item.get("target_evidence")
            and item.get("user_action")
            and item.get("acceptance")
            and item.get("upgrades")
            and "evidence_" in str(item.get("file_name") or "")
        ),
        "capture_playbook_status": capture_playbook.get("status", ""),
        "capture_playbook_step_count": len(capture_steps),
        "capture_playbook_ready_count": sum(
            1
            for item in capture_steps
            if item.get("owner") and item.get("action") and item.get("expected_artifact") and item.get("acceptance")
        ),
        "capture_playbook_command_count": len(capture_playbook.get("after_capture_commands") or []),
        "claim_report_status_code": claim_response.status_code,
        "claim_level": claim_report.get("claim_level", ""),
        "can_claim_full_automation": bool(claim_report.get("can_claim_full_automation")),
        "claim_upgrade_checklist_count": len(upgrade_checklist),
        "evidence_claim_readiness": evidence_status_summary.get("claim_readiness", ""),
        "evidence_can_claim_final_report": evidence_status_summary.get("can_claim_final_report"),
        "research_evidence_requirements_status": research_evidence_requirements.get("status", ""),
        "research_ready_for_final_claim": research_evidence_requirements.get("ready_for_final_research_claim"),
        "research_evidence_blocking_checks": list(research_evidence_requirements.get("blocking_check_ids") or []),
        "placeholder_demo_source_count": (evidence_status_summary.get("counts") or {}).get("placeholder_demo_source", 0),
        "pending_evidence_count": (evidence_status_summary.get("counts") or {}).get("pending_account_or_manual_capture", 0),
    }


def verify_research_office_readiness() -> dict[str, Any]:
    errors: list[str] = []
    artifact_package = _verify_artifact_package(errors)
    demo_endpoint = _verify_demo_endpoint(errors)
    return {
        "status": "passed" if not errors else "failed",
        "mode": "research_office_no_key_readiness",
        "summary": (
            "Research office can produce a traceable staged research package and public demo downloads."
            if not errors
            else "Research office readiness found gaps."
        ),
        "artifact_package": artifact_package,
        "demo_endpoint": demo_endpoint,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    package = payload.get("artifact_package") or {}
    quality = package.get("quality") or {}
    demo = payload.get("demo_endpoint") or {}
    lines = [
        "# Research Office Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Summary: {payload.get('summary')}",
        "",
        "## Artifact Package",
        "",
        f"- Artifact count: {package.get('artifact_count')}",
        f"- Quality status: {quality.get('status')} ({quality.get('score')})",
        f"- Missing artifacts: {', '.join(package.get('missing_artifacts') or []) or '-'}",
        f"- Screenshot plan: {package.get('has_screenshot_plan')}",
        f"- Evidence gap cards: {package.get('has_evidence_gap_cards')}",
        f"- Source trace: {package.get('has_source_trace')}",
        f"- Data table: {package.get('has_data_table')}",
        f"- Competitor table: {package.get('has_competitor_table')}",
        "",
        "## Schema Gates",
        "",
        "| Artifact | Schema | Status |",
        "| --- | --- | --- |",
    ]
    for artifact_type, gate in (package.get("schema_gates") or {}).items():
        lines.append(
            f"| {artifact_type} | {gate.get('schema_id', '')} | {gate.get('status', '')} |"
        )

    lines.extend(
        [
            "",
            "## Public Demo",
            "",
            f"- HTTP: {demo.get('status_code')}",
            f"- Mode: {demo.get('mode')}",
            f"- Requires API key: {demo.get('requires_api_key')}",
            f"- Calls real models: {demo.get('calls_real_models')}",
            f"- Downloads: {demo.get('download_count')}",
        f"- Evidence boundaries: {demo.get('evidence_boundary_count')}",
        f"- Human/account boundaries: {demo.get('human_or_account_boundary_count')}",
        f"- Evidence claim readiness: {demo.get('evidence_claim_readiness')} / final_report={demo.get('evidence_can_claim_final_report')}",
        f"- Research evidence requirements: {demo.get('research_evidence_requirements_status')} / final_ready={demo.get('research_ready_for_final_claim')} / blocking={', '.join(demo.get('research_evidence_blocking_checks') or [])}",
        f"- Evidence status counts: placeholder={demo.get('placeholder_demo_source_count')}, pending={demo.get('pending_evidence_count')}",
        f"- Reading guide: {demo.get('reading_guide_ready_count')}/{demo.get('reading_guide_count')}",
        f"- Evidence handoff: {demo.get('evidence_handoff_ready_count')}/{demo.get('evidence_handoff_count')}",
        f"- Evidence gap cards: {demo.get('evidence_gap_card_ready_count')}/{demo.get('evidence_gap_card_count')}",
        f"- Evidence capture playbook: {demo.get('capture_playbook_status')} / steps={demo.get('capture_playbook_ready_count')}/{demo.get('capture_playbook_step_count')} / commands={demo.get('capture_playbook_command_count')}",
        f"- Claim report: HTTP {demo.get('claim_report_status_code')} / {demo.get('claim_level')} / full_automation={demo.get('can_claim_full_automation')}",
        f"- Claim upgrade checklist: {demo.get('claim_upgrade_checklist_count')} items",
        f"- Public demo boundary: {demo.get('public_demo_boundary')}",
        ]
    )
    for item in demo.get("downloads") or []:
        lines.append(f"  - `{item.get('uri')}`: HTTP {item.get('status_code')}, {item.get('bytes')} bytes")

    if quality.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in quality["warnings"])
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify research-office staged delivery readiness.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = verify_research_office_readiness()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
