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
        "## Primary Office Standards",
        "",
        "| Standard | Required gates |",
        "| --- | --- |",
    ]
    for standard in audit.get("primary_standards", {}).values():
        lines.append(
            f"| {standard.get('label')} | {', '.join(standard.get('required_gates', []))} |"
        )

    lines.extend(
        [
            "",
            "## Office Results",
            "",
            "| Office | Role | Protocol | Launch gates | Can be primary | Missing protocol fields |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for office in audit.get("offices", []):
        missing = ", ".join(office.get("missing_profile_fields", [])) or "-"
        lines.append(
            "| {office_id} | {role} | {protocol} | {launch} | {primary} | {missing} |".format(
                office_id=office.get("office_id"),
                role=office.get("role"),
                protocol=office.get("protocol_status"),
                launch=office.get("launch_gate_status"),
                primary=str(bool(office.get("can_be_primary"))).lower(),
                missing=missing,
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
