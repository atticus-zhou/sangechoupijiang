"""Run the public-release readiness gate without real model calls."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


RELEASE_CHECKS = [
    {
        "id": "first_run",
        "title": "First-run guidance",
        "command": ["scripts/verify_first_run_readiness.py", "--format", "json"],
    },
    {
        "id": "productization_status",
        "title": "Productization objective coverage",
        "command": ["scripts/verify_productization_status.py", "--format", "json"],
    },
    {
        "id": "model_guidance",
        "title": "Model configuration guidance",
        "command": ["scripts/verify_model_configuration_guidance.py", "--format", "json"],
    },
    {
        "id": "development_checklist",
        "title": "Developer post-change checklist",
        "command": ["scripts/verify_development_checklist.py", "--format", "json", "--skip-release"],
    },
    {
        "id": "github_release_contract",
        "title": "GitHub release evidence contract",
        "command": ["scripts/verify_github_release_evidence.py", "--format", "json", "--contract-only"],
    },
    {
        "id": "public_docs_readability",
        "title": "Public docs readability",
        "command": ["scripts/verify_public_docs_readability.py", "--format", "json"],
    },
    {
        "id": "runtime_health",
        "title": "Runtime health endpoint contract",
        "command": ["scripts/verify_runtime_health_contract.py", "--format", "json"],
    },
    {
        "id": "public_demo",
        "title": "Public no-key demo",
        "command": ["scripts/verify_public_demo_mode.py", "--format", "json"],
    },
    {
        "id": "static_showcase_export",
        "title": "Export backend-free static showcase",
        "command": ["scripts/export_public_showcase.py", "--output", "dist/public-showcase", "--format", "json"],
    },
    {
        "id": "static_showcase",
        "title": "Backend-free static showcase export",
        "command": ["scripts/verify_static_public_showcase.py", "--format", "json", "--existing-dir", "dist/public-showcase"],
    },
    {
        "id": "portfolio_showcase_sync",
        "title": "Portfolio showcase copy sync",
        "command": ["scripts/verify_portfolio_showcase_sync.py", "--format", "json"],
    },
    {
        "id": "comic_delivery",
        "title": "AI comic Word canvas delivery",
        "command": ["scripts/verify_comic_v2_delivery.py", "--format", "json"],
    },
    {
        "id": "comic_downstream_handoff",
        "title": "AI comic downstream handoff",
        "command": ["scripts/verify_comic_v2_downstream_handoff.py", "--format", "json"],
    },
    {
        "id": "comic_production_benchmark",
        "title": "AI comic production quality benchmark",
        "command": ["scripts/verify_comic_v2_production_benchmark.py", "--format", "json"],
    },
    {
        "id": "comic_real_production_claim",
        "title": "AI comic real production claim boundary",
        "command": ["scripts/verify_comic_real_production_claim.py", "--format", "json"],
    },
    {
        "id": "comic_real_quality_upgrade_plan",
        "title": "AI comic real quality upgrade plan",
        "command": ["scripts/verify_comic_real_quality_upgrade_plan.py", "--format", "json"],
    },
    {
        "id": "public_comic_trace_bundle",
        "title": "Public AI comic trace bundle",
        "command": ["scripts/verify_public_comic_trace_bundle.py", "--format", "json"],
    },
    {
        "id": "comic_handoff_inventory",
        "title": "AI comic handoff inventory",
        "command": ["scripts/audit_comic_v2_handoffs.py", "--root", "output/comic_v2_production_benchmark", "--format", "json"],
    },
    {
        "id": "research_readiness",
        "title": "Research office staged delivery",
        "command": ["scripts/verify_research_office_readiness.py", "--format", "json"],
    },
    {
        "id": "office_governance",
        "title": "Office extension governance",
        "command": ["scripts/verify_office_extension_governance.py", "--format", "json"],
    },
    {
        "id": "future_office_backlog",
        "title": "Future office backlog boundary",
        "command": ["scripts/verify_future_office_backlog.py", "--format", "json"],
    },
    {
        "id": "office_schema_registry",
        "title": "Office schema gate registry",
        "command": ["scripts/verify_office_schema_registry.py", "--format", "json"],
    },
    {
        "id": "office_recovery_registry",
        "title": "Office recovery registry",
        "command": ["scripts/verify_office_recovery_registry.py", "--format", "json"],
    },
    {
        "id": "office_isolation",
        "title": "Office isolation",
        "command": ["scripts/verify_office_isolation.py", "--format", "json"],
    },
    {
        "id": "product_readiness",
        "title": "Product readiness with deterministic E2E",
        "command": ["scripts/verify_product_readiness.py", "--format", "json", "--run-e2e"],
    },
    {
        "id": "secret_scan",
        "title": "Secret and runtime artifact scan",
        "command": ["scripts/check_no_secrets.py"],
    },
]


def _run_check(check: dict[str, Any]) -> dict[str, Any]:
    command = [sys.executable, *check["command"]]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    parsed: dict[str, Any] | None = None
    if stdout.strip().startswith("{"):
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "id": check["id"],
        "title": check["title"],
        "command": "python " + " ".join(check["command"]),
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "summary": _summary_for(check["id"], parsed, stdout, stderr),
        "parsed_status": (parsed or {}).get("status", ""),
        "stdout_tail": "\n".join(stdout.strip().splitlines()[-8:]),
        "stderr_tail": "\n".join(stderr.strip().splitlines()[-8:]),
    }


def _summary_for(check_id: str, parsed: dict[str, Any] | None, stdout: str, stderr: str) -> str:
    if parsed:
        if check_id == "public_demo":
            demos = parsed.get("demos") or {}
            showcase = parsed.get("showcase_manifest") or {}
            return (
                f"{len(demos)} demos; "
                f"showcase={showcase.get('status_code')}; "
                f"fast_review={showcase.get('fast_review_ready_count')}/{showcase.get('fast_review_count')}; "
                f"reading_guide={showcase.get('reading_guide_ready_count')}/{showcase.get('reading_guide_count')}; "
                f"quick_start={showcase.get('downstream_quick_start_ready_count')}/{showcase.get('downstream_quick_start_count')}; "
                f"interview_script={showcase.get('interview_script_ready_count')}/{showcase.get('interview_script_count')}; "
                f"reproducibility={showcase.get('reproducibility_ready_count')}/{showcase.get('reproducibility_count')}; "
                f"badge={showcase.get('release_badge_status')}; "
                f"mode={parsed.get('mode')}"
            )
        if check_id == "static_showcase":
            return (
                f"files={parsed.get('file_count')}; "
                f"downloads={parsed.get('download_count')}; "
                f"catalog={parsed.get('download_catalog_count')}; "
                f"fast_review={parsed.get('fast_review_ready_count')}/{parsed.get('fast_review_count')}; "
                f"reading_guide={parsed.get('reading_guide_ready_count')}/{parsed.get('reading_guide_count')}; "
                f"quick_start={parsed.get('downstream_quick_start_ready_count')}/{parsed.get('downstream_quick_start_count')}; "
                f"post_run={parsed.get('post_run_validation_ready_count')}/{parsed.get('post_run_validation_count')}; "
                f"visitor_route={parsed.get('visitor_acceptance_step_count')}; "
                f"download_acceptance={parsed.get('visitor_acceptance_download_count')}; "
                f"handoff_recovery={parsed.get('handoff_inventory_recovery_item_count')}:{','.join(parsed.get('handoff_inventory_recovery_actions') or [])}; "
                f"backend={parsed.get('requires_backend')}; "
                f"text_integrity={parsed.get('text_integrity_status')}; "
                f"prompt_quality={parsed.get('comic_prompt_quality_status')}; "
                f"prompt_issues={parsed.get('comic_prompt_issue_count')}; "
                f"research_claim={parsed.get('research_claim_level')}; "
                f"research_full_auto={parsed.get('research_can_claim_full_automation')}"
            )
        if check_id == "static_showcase_export":
            return (
                f"files={parsed.get('file_count')}; "
                f"downloads={parsed.get('download_count')}; "
                f"entrypoint={parsed.get('entrypoint')}; "
                f"text_integrity={parsed.get('text_integrity_status')}; "
                f"backend={parsed.get('requires_backend')}; "
                f"api_key={parsed.get('requires_api_key')}; "
                f"real_models={parsed.get('calls_real_models')}"
            )
        if check_id == "runtime_health":
            return (
                f"endpoint={parsed.get('endpoint')}; "
                f"alias={parsed.get('alias')}; "
                f"service={parsed.get('service')}; "
                f"offices={parsed.get('office_count')}; "
                f"public_safe={parsed.get('public_safe')}; "
                f"credentials={parsed.get('requires_model_credentials')}; "
                f"real_models={parsed.get('calls_real_models')}"
            )
        if check_id == "portfolio_showcase_sync":
            return (
                f"status={parsed.get('status')}; "
                f"compared={parsed.get('compared_files')}/{parsed.get('source_file_count')}; "
                f"missing={len(parsed.get('missing_files') or [])}; "
                f"mismatched={len(parsed.get('mismatched_files') or [])}; "
                f"extra={len(parsed.get('extra_files') or [])}; "
                f"target_source={parsed.get('target_source')}; "
                f"live_external=True"
            )
        if check_id == "comic_delivery":
            return (
                f"handoff_ready={parsed.get('handoff_ready')}; "
                f"assets={parsed.get('asset_count')}; "
                f"shots={parsed.get('shot_count')}; "
                f"embedded_images={parsed.get('embedded_images')}; "
                f"quick_start={parsed.get('handoff_manifest_downstream_quick_start_steps')}"
            )
        if check_id == "comic_downstream_handoff":
            return (
                f"downstream_handoff_ready={parsed.get('downstream_handoff_ready')}; "
                f"assets={parsed.get('asset_count')}; "
                f"images={parsed.get('image_count')}; "
                f"shots={parsed.get('shot_count')}; "
                f"structured_director_shots={parsed.get('structured_director_shots')}; "
                f"quick_start={parsed.get('quick_start_step_count')}"
            )
        if check_id == "comic_production_benchmark":
            prompt_quality = parsed.get("prompt_quality_summary") or {}
            return (
                f"score={parsed.get('package_quality_score')}; "
                f"claim={parsed.get('quality_claim')}; "
                f"visual_evidence={parsed.get('visual_evidence_level')}; "
                f"real_quality_verified={parsed.get('production_quality_verified')}; "
                f"prompt_quality={prompt_quality.get('status')}; "
                f"prompt_issues={prompt_quality.get('issue_count')}"
            )
        if check_id == "comic_real_production_claim":
            recovery = parsed.get("claim_upgrade_recovery") or {}
            return (
                f"claim_level={parsed.get('claim_level')}; "
                f"public_show={parsed.get('can_publicly_show')}; "
                f"real_quality={parsed.get('can_claim_real_quality')}; "
                f"downstream={parsed.get('downstream_status')}; "
                f"upgrade_checklist={len(parsed.get('claim_upgrade_checklist') or [])}; "
                f"recovery={recovery.get('recovery_action')}; "
                f"recovery_steps={len(recovery.get('steps') or [])}"
            )
        if check_id == "comic_real_quality_upgrade_plan":
            return (
                f"current={parsed.get('current_claim_level')}; "
                f"target={parsed.get('target_claim_level')}; "
                f"status={parsed.get('upgrade_status')}; "
                f"steps={parsed.get('operator_step_count')}; "
                f"models={','.join(parsed.get('model_preflight_departments') or [])}; "
                f"recovery={parsed.get('recovery_action')}"
            )
        if check_id == "public_comic_trace_bundle":
            return (
                f"assets={parsed.get('asset_count')}; "
                f"images={parsed.get('image_count')}; "
                f"shots={parsed.get('shot_count')}; "
                f"claim={parsed.get('claim_level')}; "
                f"visual={parsed.get('visual_evidence_level')}; "
                f"real_quality={parsed.get('production_quality_verified')}; "
                f"supports_real_quality={parsed.get('supports_real_quality_claim')}; "
                f"upgrade_checklist={parsed.get('upgrade_checklist_count')}; "
                f"reproducibility={parsed.get('reproducibility_command_count')}"
            )
        if check_id == "office_schema_registry":
            return (
                f"providers={','.join(parsed.get('provider_offices') or [])}; "
                f"bindings={parsed.get('passed_binding_count')}/{parsed.get('binding_count')}; "
                f"errors={parsed.get('error_count')}"
            )
        if check_id == "office_recovery_registry":
            return (
                f"offices={','.join(parsed.get('offices_with_actions') or [])}; "
                f"bindings={parsed.get('passed_binding_count')}/{parsed.get('binding_count')}; "
                f"errors={parsed.get('error_count')}"
            )
        if check_id == "comic_handoff_inventory":
            return (
                f"manifests={parsed.get('manifest_count')}; "
                f"production_verified={parsed.get('production_verified_count')}; "
                f"demo_only={parsed.get('demo_only_count')}; "
                f"needs_review={parsed.get('needs_review_count')}"
            )
        if check_id == "research_readiness":
            package = parsed.get("artifact_package") or {}
            quality = package.get("quality") or {}
            demo = parsed.get("demo_endpoint") or {}
            return (
                f"quality={quality.get('status')}:{quality.get('score')}; "
                f"downloads={demo.get('download_count')}; "
                f"reading_guide={demo.get('reading_guide_ready_count')}/{demo.get('reading_guide_count')}; "
                f"handoff={demo.get('evidence_handoff_ready_count')}/{demo.get('evidence_handoff_count')}; "
                f"capture={demo.get('capture_playbook_ready_count')}/{demo.get('capture_playbook_step_count')}; "
                f"claim={demo.get('claim_level')}; "
                f"full_auto={demo.get('can_claim_full_automation')}; "
                f"upgrade_checklist={demo.get('claim_upgrade_checklist_count')}"
            )
        if check_id == "office_governance":
            demo_contract = parsed.get("required_demo_contract") or []
            starter = parsed.get("starter_checklist_audit") or {}
            schema_registry = parsed.get("schema_registry_audit") or {}
            recovery_registry = parsed.get("recovery_registry_audit") or {}
            return (
                f"primary={','.join(parsed.get('primary_office_ids') or [])}; "
                f"offices={len(parsed.get('offices') or [])}; "
                f"demo_contract={len(demo_contract)}; "
                f"starter={starter.get('status')}; "
                f"starter_items={starter.get('count')}; "
                f"schema_bindings={schema_registry.get('passed_binding_count')}/{schema_registry.get('binding_count')}; "
                f"recovery_bindings={recovery_registry.get('passed_binding_count')}/{recovery_registry.get('binding_count')}"
            )
        if check_id == "future_office_backlog":
            return (
                f"candidates={parsed.get('blocked_candidate_count')}/{parsed.get('candidate_count')}; "
                f"backlog={parsed.get('backlog_count')}; "
                f"ids={','.join(parsed.get('candidate_ids') or [])}; "
                f"platform={','.join(parsed.get('backlog_ids') or [])}"
            )
        if check_id == "office_isolation":
            checks = parsed.get("checks") or []
            failed = [item for item in checks if item.get("status") != "passed"]
            offices = ",".join(parsed.get("offices") or [])
            return f"offices={offices}; checks={len(checks)}; failures={len(failed)}"
        if check_id == "product_readiness":
            runtime = parsed.get("runtime_verification") or {}
            stage_b = runtime.get("stage_b_product_loop") or {}
            return f"status={parsed.get('status')}; stage_b={stage_b.get('status')}"
        if check_id == "first_run":
            checklist = parsed.get("github_download_checklist") or {}
            deployment_modes = parsed.get("deployment_mode_matrix") or []
            return (
                f"mode={parsed.get('mode')}; "
                f"paths={','.join(parsed.get('recommended_order') or [])}; "
                f"deployment_modes={len(deployment_modes)}; "
                f"github_download={checklist.get('status')}:"
                f"{checklist.get('present_public_file_count')}/{checklist.get('expected_public_file_count')}; "
                f"private_boundaries={len(checklist.get('private_paths_never_commit') or [])}"
            )
        if check_id == "productization_status":
            return (
                f"requirements={len(parsed.get('requirements') or [])}; "
                f"doc={parsed.get('document')}; "
                f"readme_linked={parsed.get('readme_links_status')}"
            )
        if check_id == "model_guidance":
            return (
                f"checks={len(parsed.get('checks') or [])}; "
                f"offices={len(parsed.get('office_model_setup_summary') or [])}; "
                f"comic_ladder={len(parsed.get('comic_setup_ladder') or [])}; "
                f"mode={parsed.get('mode')}"
            )
        if check_id == "development_checklist":
            return (
                f"checks={len(parsed.get('checks') or [])}; "
                f"changed_files={parsed.get('changed_files')}; "
                f"skip_release={parsed.get('skip_release')}; "
                f"mode={parsed.get('mode')}"
            )
        if check_id == "github_release_contract":
            return (
                f"checks={len(parsed.get('checks') or [])}; "
                f"artifact={parsed.get('artifact_name')}; "
                f"failures={len(parsed.get('failures') or [])}; "
                f"mode={parsed.get('mode')}"
            )
        if check_id == "public_docs_readability":
            return (
                f"docs={parsed.get('passed_count')}/{parsed.get('doc_count')}; "
                f"failures={parsed.get('failed_count')}; "
                f"mode={parsed.get('mode')}"
            )
        return str(parsed.get("summary") or parsed.get("status") or "parsed json")
    text = (stdout or stderr).strip()
    return text.splitlines()[-1] if text else "no output"


def verify_release_readiness() -> dict[str, Any]:
    checks = [_run_check(check) for check in RELEASE_CHECKS]
    failures = [item for item in checks if item["status"] != "passed"]
    return {
        "status": "passed" if not failures else "failed",
        "mode": "public_release_readiness",
        "safe_for_public_release": not failures,
        "summary": (
            "All no-key release gates passed."
            if not failures
            else f"{len(failures)} release gates failed."
        ),
        "checks": checks,
        "failures": [item["id"] for item in failures],
        "commands": [item["command"] for item in checks],
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Release Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Safe for public release: `{payload.get('safe_for_public_release')}`",
        f"Summary: {payload.get('summary')}",
        "",
        "| Check | Status | Summary | Command |",
        "| --- | --- | --- | --- |",
    ]
    for check in payload.get("checks", []):
        lines.append(
            f"| {check.get('title')} | {check.get('status')} | "
            f"{str(check.get('summary', '')).replace('|', '/')} | `{check.get('command')}` |"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for check in payload["checks"]:
            if check["status"] == "passed":
                continue
            lines.append(f"### {check['id']}")
            if check.get("stdout_tail"):
                lines.extend(["", "stdout:", "```", check["stdout_tail"], "```"])
            if check.get("stderr_tail"):
                lines.extend(["", "stderr:", "```", check["stderr_tail"], "```"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run public-release readiness gates.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = verify_release_readiness()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
