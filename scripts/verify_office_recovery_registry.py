"""Verify that office recovery actions have actionable retry contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.office_recovery_registry import audit_office_recovery_registry


def format_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Office Recovery Registry Audit",
        "",
        f"Status: `{audit.get('status')}`",
        f"Offices with actions: `{', '.join(audit.get('offices_with_actions') or [])}`",
        f"Bindings: `{audit.get('passed_binding_count')}/{audit.get('binding_count')}`",
        "",
        "## Recovery Actions",
        "",
        "| Office | Stage | Method | Path | Preserves | Clears | Status | Errors |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in audit.get("bindings") or []:
        lines.append(
            "| {office} | {stage} | {method} | {path} | {preserves} | {clears} | {status} | {errors} |".format(
                office=item.get("office_id", ""),
                stage=item.get("stage", ""),
                method=item.get("method", ""),
                path=item.get("path_template", ""),
                preserves=", ".join(item.get("preserves") or []),
                clears=", ".join(item.get("clears") or []),
                status=item.get("status", ""),
                errors="; ".join(item.get("errors") or []) or "-",
            )
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    audit = audit_office_recovery_registry()
    if args.format == "json":
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(audit))
    return 0 if audit.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
