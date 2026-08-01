"""Verify that office schema-gate declarations are backed by validators."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.office_schema_registry import audit_office_schema_gate_registry


def format_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Office Schema Gate Registry Audit",
        "",
        f"Status: `{audit.get('status')}`",
        f"Providers: `{', '.join(audit.get('provider_offices') or [])}`",
        f"Offices with declared gates: `{', '.join(audit.get('offices_with_declared_gates') or [])}`",
        f"Bindings: `{audit.get('passed_binding_count')}/{audit.get('binding_count')}`",
        "",
        "## Bindings",
        "",
        "| Office | Schema | Artifact | Owner | Stage | Binding | Status | Errors |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in audit.get("bindings") or []:
        errors = "; ".join(item.get("errors") or [])
        lines.append(
            "| {office} | {schema} | {artifact} | {owner} | {stage} | {binding} | {status} | {errors} |".format(
                office=item.get("office_id", ""),
                schema=item.get("schema_id", ""),
                artifact=item.get("artifact_type", ""),
                owner=item.get("owner_agent", ""),
                stage=item.get("stage", ""),
                binding=item.get("binding_status", ""),
                status=item.get("status", ""),
                errors=errors or "-",
            )
        )
    if audit.get("missing_provider_offices"):
        lines.extend([
            "",
            "## Missing Providers",
            "",
            ", ".join(audit.get("missing_provider_offices") or []),
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    audit = audit_office_schema_gate_registry()
    if args.format == "json":
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(audit))
    return 0 if audit.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
