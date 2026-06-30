"""Run a local first-run diagnosis without calling model providers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config_manager import ConfigManager
from src.offices import get_office
from src.office_preflight import build_office_preflight
from src.system_preflight import build_system_preflight


def build_doctor_report(base_dir: Path | str = REPO_ROOT) -> dict:
    """Return a user-facing local diagnosis for the real local product."""
    root = Path(base_dir)
    manager = ConfigManager(base_dir=str(root))
    system = build_system_preflight(manager, base_dir=root)
    office = build_office_preflight(
        "comic_production",
        manager.get_model_config,
        base_dir=root,
    )
    offices = _build_office_availability(manager, root)
    status = _overall_status(system.get("status", "blocked"), office.get("status", "blocked"))
    return {
        "product": "三个臭皮匠",
        "mode": "local_real_product",
        "status": status,
        "summary": _summary(status),
        "next_action": _next_action(system, office),
        "system": system,
        "office": office,
        "offices": offices,
    }


def format_doctor_markdown(report: dict) -> str:
    lines = [
        "# 三个臭皮匠本地自检",
        "",
        f"- 状态：{report.get('status', '')}",
        f"- 模式：{report.get('mode', '')}",
        f"- 摘要：{report.get('summary', '')}",
        f"- 下一步：{report.get('next_action', '')}",
        "",
        "## 系统启动检查",
        "",
        "| 项目 | 状态 | 影响 | 下一步 |",
        "| --- | --- | --- | --- |",
    ]
    for item in report.get("system", {}).get("checks", []):
        lines.append(_row(item.get("title"), item.get("status"), item.get("impact"), item.get("next_action")))
    lines.extend([
        "",
        "## 办公室可用性",
        "",
        "| 办公室 | 状态 | 摘要 | 下一步 |",
        "| --- | --- | --- | --- |",
    ])
    for item in report.get("offices", []):
        lines.append(_row(item.get("name"), item.get("status"), item.get("summary"), item.get("next_action")))
    lines.extend([
        "",
        "## AI 漫剧制片办公室能力",
        "",
        "| 能力 | 状态 | 负责 | 影响 | 下一步 |",
        "| --- | --- | --- | --- | --- |",
    ])
    for item in report.get("office", {}).get("capabilities", []):
        owner = item.get("owner_label", "")
        model_kind = item.get("model_kind", "")
        lines.append(_row(item.get("title"), item.get("status"), f"{owner}{model_kind}：{item.get('impact', '')}", item.get("next_action")))
    return "\n".join(lines)


def _build_office_availability(manager: ConfigManager, root: Path) -> list[dict]:
    offices = []
    for office_id in ("research", "comic_production"):
        profile = get_office(office_id)
        preflight = build_office_preflight(
            office_id,
            manager.get_model_config,
            base_dir=root,
        )
        offices.append({
            "office_id": preflight.get("office_id", office_id),
            "name": profile.name,
            "status": preflight.get("status", "blocked"),
            "summary": preflight.get("summary", ""),
            "next_action": preflight.get("next_action", ""),
            "blocking_reasons": preflight.get("blocking_reasons", []),
            "capability_count": len(preflight.get("capabilities", [])),
        })
    return offices


def _overall_status(system_status: str, office_status: str) -> str:
    if "blocked" in {system_status, office_status}:
        return "blocked"
    if "partial" in {system_status, office_status}:
        return "partial"
    if "missing" in {system_status, office_status}:
        return "partial"
    return "ready"


def _summary(status: str) -> str:
    if status == "ready":
        return "本地环境和 AI 漫剧制片办公室关键能力可用。"
    if status == "partial":
        return "本地环境可启动，但部分模型能力缺失；可以先推进不依赖该能力的阶段。"
    return "存在阻塞项；请先按下一步建议修复后再开始真实生产。"


def _next_action(system: dict, office: dict) -> str:
    if system.get("status") == "blocked":
        return system.get("next_action", "先修复本地启动条件。")
    if office.get("status") in {"blocked", "partial", "missing"}:
        return office.get("next_action", "打开模型页面补齐缺失能力。")
    return "可以运行 python run.py --port 8080，并进入 AI 漫剧制片办公室。"


def _row(*values: object) -> str:
    return "| " + " | ".join(_cell(value) for value in values) + " |"


def _cell(value: object) -> str:
    return str(value or "").replace("\n", " ").replace("|", "／")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="三个臭皮匠本地自检")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    report = build_doctor_report(REPO_ROOT)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_doctor_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
