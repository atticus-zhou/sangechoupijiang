"""Verify every primary office exposes a clear runtime delivery acceptance card."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config_manager import ConfigManager
from src.office_runtime import build_office_runtime_status


RESEARCH_TYPES = [
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
]


def verify_office_runtime_acceptance() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        manager = ConfigManager(base_dir=tmp)
        _seed_research_workspace(manager)
        _seed_comic_workspace(manager)

        statuses = {
            "research": build_office_runtime_status(manager, "ws-runtime-acceptance-research"),
            "comic_production": build_office_runtime_status(manager, "ws-runtime-acceptance-comic"),
        }

    audits = {
        office_id: _audit_status(office_id, status)
        for office_id, status in statuses.items()
    }
    errors = [
        f"{office_id}: {error}"
        for office_id, audit in audits.items()
        for error in audit["errors"]
    ]

    return {
        "status": "passed" if not errors else "failed",
        "mode": "office_runtime_acceptance_contract",
        "office_count": len(statuses),
        "offices": sorted(statuses),
        "acceptance_statuses": {
            office_id: (status.get("delivery_acceptance") or {}).get("status", "")
            for office_id, status in statuses.items()
        },
        "download_labels": {
            office_id: (status.get("delivery_acceptance") or {}).get("downloads", {})
            for office_id, status in statuses.items()
        },
        "audit": audits,
        "errors": errors,
    }


def _seed_research_workspace(manager: ConfigManager) -> None:
    workspace_id = "ws-runtime-acceptance-research"
    task_id = "task-runtime-acceptance-research"
    manager.create_workspace(workspace_id, "research", "民用无人机调研验收")
    standard_report = "\n".join(
        [
            "# 民用无人机调研",
            "## 行业概览\n阶段结论、平台表现、渠道变化和用户场景已经整理。",
            "## 竞品对比\n头部品牌、价格带、卖点和评价口径已经横向比较。",
            "## 价格带与数据要点\n销量、价格、年份、平台字段和待核验项已经列明。",
            "## 用户痛点\n差评痛点和机会已经拆分。",
            "## 差异化机会\n可进入机会和风险边界已经说明。",
            "## 风险与建议\n阶段建议、证据缺口和截图计划已经列明。",
            "## 证据与待核验\n来源清单、截图清单、补证卡。",
        ]
    )
    for artifact_type in RESEARCH_TYPES:
        manager.create_artifact(
            artifact_id=f"art-runtime-acceptance-research-{artifact_type}",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type=artifact_type,
            title=f"{artifact_type} 产物",
            uri=(
                f"/api/workspaces/{workspace_id}/files/standard_report.md"
                if artifact_type == "standard_report"
                else ""
            ),
            content=(
                standard_report
                if artifact_type == "standard_report"
                else "| 字段 | 内容 |\n| --- | --- |\n| 示例 | 已补齐 |"
            ),
            metadata={"office_id": "research"},
            created_by="hubu",
        )


def _seed_comic_workspace(manager: ConfigManager) -> None:
    workspace_id = "ws-runtime-acceptance-comic"
    task_id = "task-runtime-acceptance-comic"
    manager.create_workspace(workspace_id, "comic_production", "AI 漫剧制片验收")
    benchmark = {
        "package_quality_ready": True,
        "production_quality_verified": False,
        "package_quality_score": 88,
        "visual_evidence_level": "fixture_only",
        "prompt_quality_summary": {
            "status": "ready",
            "issue_count": 0,
            "asset_prompt_count": 8,
            "shot_prompt_count": 4,
        },
        "image_quality_summary": {
            "total_images": 8,
            "usable_images": 8,
            "waste_or_rework_images": 0,
        },
    }
    manager.create_artifact(
        artifact_id="art-runtime-acceptance-comic-word",
        workspace_id=workspace_id,
        task_id=task_id,
        artifact_type="comic_v2_word_canvas",
        title="Word 制片画布",
        uri=f"/api/workspaces/{workspace_id}/files/delivery/canvas.docx",
        metadata={"office_id": "comic_production", "quality_benchmark": benchmark},
        created_by="libu",
    )
    manager.create_artifact(
        artifact_id="art-runtime-acceptance-comic-handoff",
        workspace_id=workspace_id,
        task_id=task_id,
        artifact_type="comic_v2_handoff_manifest",
        title="V2 制片引用清单",
        uri=f"/api/workspaces/{workspace_id}/files/delivery/handoff_manifest.json",
        metadata={"office_id": "comic_production", "quality_benchmark": benchmark},
        created_by="libu",
    )


def _audit_status(office_id: str, status: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    acceptance = status.get("delivery_acceptance") or {}
    downloads = acceptance.get("downloads") or {}
    items = acceptance.get("acceptance_items") or []

    for key in ("status", "title", "summary", "next_action", "quality_claim_label", "quality_claim_value"):
        if not str(acceptance.get(key) or "").strip():
            errors.append(f"delivery_acceptance.{key} is required")
    if not isinstance(items, list) or len(items) < 5:
        errors.append("delivery_acceptance.acceptance_items must explain at least five checks")
    for item in items:
        if not all(str(item.get(key) or "").strip() for key in ("id", "label", "owner", "message")):
            errors.append("each acceptance item must include id, label, owner, and message")
            break

    if office_id == "research":
        if acceptance.get("status") != "staged_report_ready":
            errors.append("research acceptance should be staged_report_ready for a complete staged package")
        if acceptance.get("can_claim_real_quality") is not False:
            errors.append("research staged package must not claim final real-data completeness")
        if downloads.get("word_canvas_label") != "下载阶段报告":
            errors.append("research report download label should be user-readable")
        if not str(downloads.get("word_canvas_uri") or "").endswith("standard_report.md"):
            errors.append("research acceptance must expose the staged report download")
        if "补齐第三方平台截图" not in str(acceptance.get("next_action") or ""):
            errors.append("research next action must explain screenshot evidence is still needed")

    if office_id == "comic_production":
        if acceptance.get("status") != "structure_ready_needs_real_quality":
            errors.append("comic fixture package should be structure_ready_needs_real_quality")
        if acceptance.get("can_handoff_to_downstream") is not False:
            errors.append("comic fixture package must not claim real downstream readiness")
        if acceptance.get("can_claim_real_quality") is not False:
            errors.append("comic fixture package must not claim real image quality")
        if downloads.get("word_canvas_label") != "下载 Word":
            errors.append("comic Word download label should be user-readable")
        if downloads.get("handoff_manifest_label") != "下载引用清单":
            errors.append("comic handoff download label should be user-readable")
        if (acceptance.get("recovery_action") or {}).get("action") != "regenerate_images":
            errors.append("comic acceptance should explain the recovery path for missing real model evidence")

    return {
        "status": "passed" if not errors else "failed",
        "acceptance_status": acceptance.get("status", ""),
        "claim": acceptance.get("quality_claim_value", ""),
        "acceptance_item_count": len(items),
        "download_count": len([value for value in downloads.values() if str(value or "").strip()]),
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Office Runtime Acceptance Contract",
        "",
        f"Status: `{payload['status']}`",
        f"Mode: `{payload['mode']}`",
        f"Offices: `{', '.join(payload.get('offices') or [])}`",
        "",
        "| Office | Status | Acceptance items | Downloads | Claim |",
        "| --- | --- | --- | --- | --- |",
    ]
    for office_id, audit in (payload.get("audit") or {}).items():
        lines.append(
            f"| {office_id} | {audit.get('acceptance_status')} | "
            f"{audit.get('acceptance_item_count')} | {audit.get('download_count')} | "
            f"{audit.get('claim')} |"
        )
    if payload.get("errors"):
        lines.extend(["", "## Errors"])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    payload = verify_office_runtime_acceptance()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
