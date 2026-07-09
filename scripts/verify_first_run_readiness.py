"""Build a first-run checklist for people cloning the project from GitHub."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.doctor import build_doctor_report
from src.product_readiness import audit_comic_production_readiness


PUBLIC_DEMO_COMMAND = "python scripts/verify_public_demo_mode.py --format markdown"
LOCAL_DOCTOR_COMMAND = "python scripts/doctor.py --format markdown"
PRODUCT_READINESS_COMMAND = "python scripts/verify_product_readiness.py --format markdown"
OFFICE_ISOLATION_COMMAND = "python scripts/verify_office_isolation.py --format markdown"
SERVER_COMMAND = "python run.py --port 8080"


def build_first_run_readiness(base_dir: Path | str = REPO_ROOT) -> dict[str, Any]:
    root = Path(base_dir)
    doctor = build_doctor_report(root)
    product = audit_comic_production_readiness(root)
    system_status = str(doctor.get("system", {}).get("status") or "blocked")
    office_status = str(doctor.get("office", {}).get("status") or "blocked")
    local_ready = system_status == "ready" and office_status == "ready"

    paths = [
        _public_demo_path(),
        _local_real_use_path(doctor, local_ready),
        _developer_extension_path(product),
    ]
    return {
        "product": "三个臭皮匠",
        "status": "ready_for_guided_first_run",
        "mode": "new_user_reproducibility",
        "safe_for_public_repo": True,
        "summary": "A GitHub-first checklist for demo viewing, local real use, and office extension.",
        "paths": paths,
        "recommended_order": [item["id"] for item in paths],
        "commands": {
            "public_demo": PUBLIC_DEMO_COMMAND,
            "local_doctor": LOCAL_DOCTOR_COMMAND,
            "product_readiness": PRODUCT_READINESS_COMMAND,
            "office_isolation": OFFICE_ISOLATION_COMMAND,
            "server": SERVER_COMMAND,
        },
        "safety_boundaries": [
            "Do not commit API Key values; use environment variables or local config.yaml only.",
            "Do not publish user_data, output, runtime_logs, browser profiles, cookies, or generated private deliverables.",
            "Public demos must stay read-only and must not call real model providers.",
        ],
        "doctor_status": doctor.get("status", ""),
        "product_readiness_status": product.get("status", ""),
    }


def _public_demo_path() -> dict[str, Any]:
    return {
        "id": "public_demo",
        "title": "公开无 Key 演示",
        "status": "ready",
        "requires_api_key": False,
        "who_it_is_for": "面试官、作品集访客、第一次看项目的人。",
        "next_action": f"Run `{PUBLIC_DEMO_COMMAND}` or open the public showcase entry in the web app.",
        "steps": [
            f"Run `{PUBLIC_DEMO_COMMAND}` to verify demo endpoints and downloads.",
            f"Start the local app with `{SERVER_COMMAND}` if you want to browse the UI.",
            "Open the office hall and choose the no-key demo entry for AI comic production or research.",
        ],
        "evidence": [
            "/api/demo/public-showcase",
            "/api/demo/comic-production/files/word_canvas.docx",
            "/api/demo/research/files/report.md",
        ],
    }


def _local_real_use_path(doctor: dict[str, Any], local_ready: bool) -> dict[str, Any]:
    blocking = list(doctor.get("system", {}).get("blocking_reasons") or [])
    blocking.extend(doctor.get("office", {}).get("blocking_reasons") or [])
    return {
        "id": "local_real_use",
        "title": "本地真实使用",
        "status": "ready" if local_ready else "needs_user_action",
        "requires_api_key": True,
        "who_it_is_for": "想用自己的模型 Key 生成真实报告或 AI 漫剧制片包的人。",
        "next_action": doctor.get("next_action") or "Run doctor, then fill missing local model configuration.",
        "steps": [
            "Copy config.example.yaml to config.yaml if config.yaml does not exist.",
            "Put API Key values in environment variables or local config.yaml, never in committed files.",
            f"Run `{LOCAL_DOCTOR_COMMAND}` and fix every blocked item it reports.",
            f"Start the app with `{SERVER_COMMAND}` and test each department from the model page.",
        ],
        "evidence": [
            f"doctor.status={doctor.get('status', '')}",
            f"system.status={doctor.get('system', {}).get('status', '')}",
            f"comic_production.status={doctor.get('office', {}).get('status', '')}",
        ],
        "blocking_reasons": blocking,
    }


def _developer_extension_path(product: dict[str, Any]) -> dict[str, Any]:
    checks = {item.get("id"): item.get("status") for item in product.get("checks", [])}
    extension_ready = all(
        checks.get(item) == "passed"
        for item in ["office_protocols", "office_isolation_contract", "office_launch_gate_audit", "agent_output_schema_gate"]
    )
    return {
        "id": "developer_extension",
        "title": "开发者扩展新办公室",
        "status": "ready" if extension_ready else "needs_user_action",
        "requires_api_key": False,
        "who_it_is_for": "想新增短视频、电商、小说或技术项目办公室的开发者。",
        "next_action": "Use the office protocol first; do not copy a one-off route into production.",
        "steps": [
            "Read /api/offices/protocols and src/offices.py before adding a new office.",
            f"Run `{OFFICE_ISOLATION_COMMAND}` after touching model config, workspaces, artifacts, or history.",
            f"Run `{PRODUCT_READINESS_COMMAND}` and keep launch gates evidence-linked.",
        ],
        "evidence": [
            f"office_protocols={checks.get('office_protocols', '')}",
            f"office_isolation_contract={checks.get('office_isolation_contract', '')}",
            f"office_launch_gate_audit={checks.get('office_launch_gate_audit', '')}",
            f"agent_output_schema_gate={checks.get('agent_output_schema_gate', '')}",
        ],
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First Run Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Safe for public repo: `{payload.get('safe_for_public_repo')}`",
        "",
        "## Recommended Order",
        "",
    ]
    for index, path_id in enumerate(payload.get("recommended_order", []), start=1):
        lines.append(f"{index}. `{path_id}`")
    lines.extend(["", "## Paths", ""])
    for item in payload.get("paths", []):
        lines.extend([
            f"### {item.get('id')} - {item.get('title')}",
            "",
            f"- Status: `{item.get('status')}`",
            f"- Requires API Key: `{item.get('requires_api_key')}`",
            f"- For: {item.get('who_it_is_for')}",
            f"- Next action: {item.get('next_action')}",
            "- Steps:",
        ])
        for step in item.get("steps", []):
            lines.append(f"  - {step}")
        lines.append("- Evidence:")
        for evidence in item.get("evidence", []):
            lines.append(f"  - `{evidence}`")
        if item.get("blocking_reasons"):
            lines.append("- Blocking reasons:")
            for reason in item.get("blocking_reasons", []):
                lines.append(f"  - {reason}")
        lines.append("")
    lines.extend(["## Safety Boundaries", ""])
    for boundary in payload.get("safety_boundaries", []):
        lines.append(f"- {boundary}")
    lines.extend(["", "## Commands", ""])
    for label, command in payload.get("commands", {}).items():
        lines.append(f"- `{label}`: `{command}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify first-run reproducibility guidance.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    payload = build_first_run_readiness(REPO_ROOT)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
