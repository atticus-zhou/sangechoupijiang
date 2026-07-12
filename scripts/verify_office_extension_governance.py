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
        "public_safety_boundaries": "说明公开模式不读取 Key、不调用真实模型、不写用户工作区。",
    }
    for field in audit.get("required_demo_contract", []):
        lines.append(f"| {field} | {demo_purposes.get(field, 'Required public demo field.')} |")

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
    if args.format == "json":
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(audit))
    return 0 if audit.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
