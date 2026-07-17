"""Verify that new offices must reuse shared productization gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.offices import audit_office_extension_governance

PROTOCOL_DOC = REPO_ROOT / "docs" / "OFFICE_EXTENSION_PROTOCOL.md"
STARTER_CHECKLIST_DOC = REPO_ROOT / "docs" / "NEW_OFFICE_STARTER_CHECKLIST.md"
PROTOCOL_DOC_MARKERS = [
    "OfficeProfile",
    "office_id",
    "最小实现包",
    "src/office_preflight.py",
    "verify_office_isolation.py",
    "no-key demo",
    "downloadable_deliverables",
    "post_run_validation",
    "跑后验收",
    "真实任务跑完后",
    "schema gates",
    "recovery_actions",
    "verify_release_readiness.py",
    "check_no_secrets.py",
    "API Key",
]
REQUIRED_STARTER_CHECKLIST_PHASES = {
    "product",
    "safety",
    "isolation",
    "workflow",
    "demo",
    "quality",
    "public_demo",
    "release",
}


def audit_protocol_doc() -> dict[str, Any]:
    doc_path = PROTOCOL_DOC.relative_to(REPO_ROOT).as_posix()
    if not PROTOCOL_DOC.exists():
        return {
            "path": doc_path,
            "status": "missing",
            "missing_markers": PROTOCOL_DOC_MARKERS,
        }
    text = PROTOCOL_DOC.read_text(encoding="utf-8")
    missing = [marker for marker in PROTOCOL_DOC_MARKERS if marker not in text]
    return {
        "path": doc_path,
        "status": "passed" if not missing else "needs_work",
        "missing_markers": missing,
    }


def audit_starter_checklist(blueprint: dict[str, Any]) -> dict[str, Any]:
    checklist = blueprint.get("starter_checklist") or []
    phases = {str(item.get("phase") or "") for item in checklist}
    missing_phases = sorted(REQUIRED_STARTER_CHECKLIST_PHASES - phases)
    incomplete_items = [
        str(item.get("id") or item.get("order") or index)
        for index, item in enumerate(checklist, start=1)
        if not item.get("id") or not item.get("question") or not item.get("evidence")
    ]
    doc_path = STARTER_CHECKLIST_DOC.relative_to(REPO_ROOT).as_posix()
    doc_missing_markers = []
    if STARTER_CHECKLIST_DOC.exists():
        doc_text = STARTER_CHECKLIST_DOC.read_text(encoding="utf-8")
        doc_markers = [
            "New Office Starter Checklist",
            "office_id",
            "downloadable_deliverables",
            "public_safety_boundaries",
            "verify_release_readiness",
            "check_no_secrets",
        ]
        doc_missing_markers = [marker for marker in doc_markers if marker not in doc_text]
    else:
        doc_missing_markers = ["missing file"]
    return {
        "status": (
            "passed"
            if checklist and not missing_phases and not incomplete_items and not doc_missing_markers
            else "needs_work"
        ),
        "count": len(checklist),
        "phases": sorted(phase for phase in phases if phase),
        "missing_phases": missing_phases,
        "incomplete_items": incomplete_items,
        "doc_path": doc_path,
        "doc_missing_markers": doc_missing_markers,
    }


def format_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Office Extension Governance Audit",
        "",
        f"Status: `{audit.get('status')}`",
        f"Mode: `{audit.get('mode')}`",
        f"Primary offices: `{', '.join(audit.get('primary_office_ids', []))}`",
        "",
        "## Required Demo Contract",
        "",
        "| Field | Purpose |",
        "| --- | --- |",
    ]
    demo_purposes = {
        "viewer_path": "告诉陌生访客先看什么、后看什么。",
        "proof_points": "说明这个办公室演示到底证明了什么。",
        "downloadable_deliverables": "提供可下载、可复核的样例交付物。",
        "deliverable_reading_guide": "解释每个交付物应该怎么看、证明什么。",
        "interview_demo_script": "给面试官或作品集访客一条 3 分钟演示路线。",
        "post_run_validation": "说明真实任务跑完后，哪些命令或证据能支撑对外声明。",
        "public_safety_boundaries": "说明公开模式不读取 Key、不调用真实模型、不写用户工作区。",
    }
    for field in audit.get("required_demo_contract", []):
        lines.append(f"| {field} | {demo_purposes.get(field, 'Required public demo field.')} |")

    blueprint = audit.get("extension_blueprint") or {}
    lines.extend(
        [
            "",
            "## Extension Blueprint",
            "",
            blueprint.get("purpose", "Future offices must follow the shared protocol."),
            "",
            "| Step | Owner | Done when | Files |",
            "| --- | --- | --- | --- |",
        ]
    )
    for step in blueprint.get("implementation_steps", []):
        lines.append(
            "| {title} | {owner} | {done_when} | {files} |".format(
                title=step.get("title", step.get("id", "")),
                owner=step.get("owner", ""),
                done_when=step.get("done_when", ""),
                files=", ".join(step.get("files", [])) or "-",
            )
        )
    if blueprint.get("minimum_implementation_package"):
        lines.extend(
            [
                "",
                "## Minimum Implementation Package",
                "",
                "| File or directory | Proves |",
                "| --- | --- |",
            ]
        )
        for item in blueprint.get("minimum_implementation_package", []):
            lines.append(f"| {item.get('file', '')} | {item.get('proves', '')} |")
    if blueprint.get("starter_checklist"):
        lines.extend(
            [
                "",
                "## New Office Starter Checklist",
                "",
                "| Step | Phase | Question | Evidence |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in blueprint.get("starter_checklist", []):
            lines.append(
                "| {order}. {id} | {phase} | {question} | {evidence} |".format(
                    order=item.get("order", ""),
                    id=item.get("id", ""),
                    phase=item.get("phase", ""),
                    question=item.get("question", ""),
                    evidence=item.get("evidence", ""),
                )
            )
    if blueprint.get("required_verifiers"):
        lines.extend(["", "Required verifiers:"])
        lines.extend(f"- `{command}`" for command in blueprint["required_verifiers"])

    protocol_doc = audit.get("protocol_doc") or {}
    starter = audit.get("starter_checklist_audit") or {}
    lines.extend(
        [
            "",
            "## Human-Readable Protocol",
            "",
            f"Path: `{protocol_doc.get('path', 'docs/OFFICE_EXTENSION_PROTOCOL.md')}`",
            f"Status: `{protocol_doc.get('status', 'missing')}`",
        ]
    )
    if protocol_doc.get("missing_markers"):
        lines.append(
            "Missing markers: `" + "`, `".join(protocol_doc.get("missing_markers", [])) + "`"
        )
    lines.extend(
        [
            "",
            "## Starter Checklist Audit",
            "",
            f"Status: `{starter.get('status', 'missing')}`",
            f"Items: `{starter.get('count', 0)}`",
            f"Phases: `{', '.join(starter.get('phases', []))}`",
            f"Document: `{starter.get('doc_path', 'docs/NEW_OFFICE_STARTER_CHECKLIST.md')}`",
        ]
    )
    if starter.get("missing_phases"):
        lines.append("Missing phases: `" + "`, `".join(starter.get("missing_phases", [])) + "`")
    if starter.get("incomplete_items"):
        lines.append("Incomplete items: `" + "`, `".join(starter.get("incomplete_items", [])) + "`")
    if starter.get("doc_missing_markers"):
        lines.append("Document missing markers: `" + "`, `".join(starter.get("doc_missing_markers", [])) + "`")

    lines.extend(
        [
            "",
            "## Primary Office Standards",
            "",
            "| Standard | Required gates |",
            "| --- | --- |",
        ]
    )
    for standard in audit.get("primary_standards", {}).values():
        lines.append(
            f"| {standard.get('label')} | {', '.join(standard.get('required_gates', []))} |"
        )

    lines.extend(
        [
            "",
            "## Office Results",
            "",
            "| Office | Role | Protocol | Launch gates | Can be primary | Missing protocol fields | Migration |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for office in audit.get("offices", []):
        missing = ", ".join(office.get("missing_profile_fields", [])) or "-"
        migration = office.get("legacy_migration") or {}
        migration_text = (
            f"{migration.get('target_office_id')} - {migration.get('action')}"
            if migration
            else "-"
        )
        lines.append(
            "| {office_id} | {role} | {protocol} | {launch} | {primary} | {missing} | {migration} |".format(
                office_id=office.get("office_id"),
                role=office.get("role"),
                protocol=office.get("protocol_status"),
                launch=office.get("launch_gate_status"),
                primary=str(bool(office.get("can_be_primary"))).lower(),
                missing=missing,
                migration=migration_text,
            )
        )

    errors = audit.get("errors") or {}
    if errors.get("protocol_errors") or errors.get("primary_errors"):
        lines.extend(["", "## Errors", ""])
        for field, values in errors.items():
            if values:
                lines.append(f"- {field}: {', '.join(values)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Verify office protocol reuse and primary-office promotion gates."
    )
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    audit = audit_office_extension_governance()
    protocol_doc = audit_protocol_doc()
    audit["protocol_doc"] = protocol_doc
    starter_checklist = audit_starter_checklist(audit.get("extension_blueprint") or {})
    audit["starter_checklist_audit"] = starter_checklist
    if protocol_doc.get("status") != "passed":
        audit["status"] = "failed"
        audit.setdefault("errors", {}).setdefault("protocol_doc_errors", []).append(
            f"{protocol_doc.get('path')} is {protocol_doc.get('status')}"
        )
    if starter_checklist.get("status") != "passed":
        audit["status"] = "failed"
        audit.setdefault("errors", {}).setdefault("starter_checklist_errors", []).append(
            "starter_checklist is incomplete"
        )
    if args.format == "json":
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(audit))
    return 0 if audit.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
