"""Export the new-office creation template for offline planning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.offices import list_office_creation_template, list_office_extension_blueprint


def export_office_creation_template(output: Path | None = None) -> dict[str, Any]:
    template = list_office_creation_template()
    blueprint = list_office_extension_blueprint()
    payload = {
        "status": "ready",
        "mode": "offline_new_office_creation_template",
        "safe_for_public_repo": True,
        "calls_real_models": False,
        "requires_api_key": False,
        "writes_workspace": False,
        "template": template,
        "blueprint": {
            "purpose": blueprint.get("purpose", ""),
            "starter_checklist_doc": blueprint.get("starter_checklist_doc", ""),
            "implementation_steps": blueprint.get("implementation_steps", []),
            "minimum_implementation_package": blueprint.get("minimum_implementation_package", []),
            "future_office_candidates": blueprint.get("future_office_candidates", []),
            "future_platform_backlog": blueprint.get("future_platform_backlog", []),
            "required_verifiers": blueprint.get("required_verifiers", []),
            "non_negotiables": blueprint.get("non_negotiables", []),
        },
        "quick_start": [
            "Pick one future office candidate or define a new user job.",
            "Copy office_profile_skeleton and replace every placeholder id/name/path.",
            "Fill public_demo_contract_skeleton before implementing UI routes.",
            "Add office-specific schema gates and recovery actions before public launch.",
            "Run release verifiers and keep blocked offices out of the primary hall.",
        ],
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    template = payload["template"]
    blueprint = payload["blueprint"]
    profile = template.get("office_profile_skeleton") or {}
    demo = template.get("public_demo_contract_skeleton") or {}
    lines = [
        "# 新办公室启动包",
        "",
        f"Status: `{payload['status']}`",
        f"Mode: `{payload['mode']}`",
        f"Requires API Key: `{payload['requires_api_key']}`",
        f"Calls real models: `{payload['calls_real_models']}`",
        f"Writes workspace: `{payload['writes_workspace']}`",
        "",
        "## 先填这两个骨架",
        "",
        f"- `office_profile_skeleton`: {len(template.get('required_profile_fields') or [])} 个必填字段。",
        f"- `public_demo_contract_skeleton`: {len(template.get('required_demo_contract') or [])} 个公开演示字段。",
        "",
        "## OfficeProfile 必填字段",
        "",
        *[f"- `{field}`" for field in template.get("required_profile_fields") or []],
        "",
        "## 上线门禁",
        "",
        *[f"- `{gate}`" for gate in template.get("required_launch_gates") or []],
        "",
        "## 上线前 Go/No-Go",
        "",
        "| Gate | Decision | Question | Evidence |",
        "| --- | --- | --- | --- |",
        *[
            "| `{id}` | `{decision}` | {question} | {evidence} |".format(
                id=item.get("id", ""),
                decision=item.get("decision", ""),
                question=item.get("question", ""),
                evidence="; ".join(item.get("required_evidence") or []),
            )
            for item in template.get("go_no_go_review") or []
        ],
        "",
        "## 最小实现包",
        "",
        "| File | Proves |",
        "| --- | --- |",
        *[
            f"| `{item.get('file', '')}` | {item.get('proves', '')} |"
            for item in blueprint.get("minimum_implementation_package") or []
        ],
        "",
        "## 快速开始",
        "",
        *[f"{index}. {step}" for index, step in enumerate(payload.get("quick_start") or [], start=1)],
        "",
        "## 骨架预览",
        "",
        f"- office id: `{profile.get('id', '')}`",
        f"- sample schema: `{(profile.get('schema_gates') or [{}])[0].get('schema_id', '')}`",
        f"- sample recovery stage: `{(profile.get('recovery_actions') or [{}])[0].get('stage', '')}`",
        f"- sample demo uri: `{((demo.get('downloadable_deliverables') or [{}])[0]).get('uri', '')}`",
        "",
        "## 后续候选办公室",
        "",
        "| Candidate | Status | Why blocked |",
        "| --- | --- | --- |",
        *[
            f"| `{item.get('id', '')}` | blocked_until_evidence | {item.get('not_ready_reason', '')} |"
            for item in blueprint.get("future_office_candidates") or []
        ],
        "",
        "## 必跑验证",
        "",
        *[f"- `{command}`" for command in blueprint.get("required_verifiers") or []],
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path, help="Optional JSON output path for the full template payload.")
    args = parser.parse_args()

    payload = export_office_creation_template(args.output)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload))


if __name__ == "__main__":
    main()
