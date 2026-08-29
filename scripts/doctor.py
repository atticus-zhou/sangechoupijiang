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
from src.offices import audit_office_launch_gates, get_office
from src.office_preflight import build_office_preflight
from src.product_readiness import audit_comic_real_production_start_readiness
from src.system_preflight import build_system_preflight


def _build_office_availability(manager: ConfigManager, root: Path) -> list[dict]:
    offices = []
    for office_id in ("research", "comic_production"):
        profile = get_office(office_id)
        preflight = build_office_preflight(
            office_id,
            manager.get_model_config,
            base_dir=root,
        )
        launch_gate = audit_office_launch_gates(office_id)
        launch_gates = launch_gate.get("gates", [])
        launch_gate_passed = sum(1 for gate in launch_gates if gate.get("status") == "passed")
        launch_gate_next = next((gate.get("next_action", "") for gate in launch_gates if gate.get("status") != "passed"), "保持门禁证据随办公室流程同步更新。")
        offices.append({
            "office_id": preflight.get("office_id", office_id),
            "name": profile.name,
            "status": preflight.get("status", "blocked"),
            "summary": preflight.get("summary", ""),
            "next_action": preflight.get("next_action", ""),
            "blocking_reasons": preflight.get("blocking_reasons", []),
            "capability_count": len(preflight.get("capabilities", [])),
            "launch_gate_status": launch_gate.get("status", "needs_work"),
            "launch_gate_passed": launch_gate_passed,
            "launch_gate_total": len(launch_gates),
            "launch_gate_next_action": launch_gate_next,
        })
    return offices


def _doctor_safe_real_production(payload: dict) -> dict:
    """Keep doctor output user-safe without changing the public API contract."""
    safe = dict(payload)
    if "requires_api_key_to_check" in safe:
        safe["requires_model_key_to_check"] = safe.pop("requires_api_key_to_check")
    return safe


def _overall_status(system_status: str, office_status: str) -> str:
    if "blocked" in {system_status, office_status}:
        return "blocked"
    if "partial" in {system_status, office_status}:
        return "partial"
    if "missing" in {system_status, office_status}:
        return "partial"
    return "ready"


def _row(*values: object) -> str:
    return "| " + " | ".join(_cell(value) for value in values) + " |"


def _cell(value: object) -> str:
    return str(value or "").replace("\n", " ").replace("|", "／")


def build_doctor_report(base_dir: Path | str = REPO_ROOT) -> dict:
    """Return a readable local diagnosis for the real local product."""
    root = Path(base_dir)
    manager = ConfigManager(base_dir=str(root))
    system = build_system_preflight(manager, base_dir=root)
    office = build_office_preflight(
        "comic_production",
        manager.get_model_config,
        base_dir=root,
    )
    real_production = _doctor_safe_real_production(
        audit_comic_real_production_start_readiness(
            manager.get_model_config,
            base_dir=root,
        )
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
        "real_production": real_production,
        "offices": offices,
    }


def format_doctor_markdown(report: dict) -> str:
    real = report.get("real_production") or {}
    inventory = real.get("handoff_inventory") or {}
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
        "## 办公室上线门禁",
        "",
        "| 办公室 | 门禁状态 | 通过项 | 下一步 |",
        "| --- | --- | --- | --- |",
    ])
    for item in report.get("offices", []):
        passed = item.get("launch_gate_passed", 0)
        total = item.get("launch_gate_total", 0)
        lines.append(_row(item.get("name"), item.get("launch_gate_status"), f"{passed}/{total}", item.get("launch_gate_next_action")))

    lines.extend([
        "",
        "## AI 漫剧制片办公室能力",
        "",
        "| 能力 | 状态 | 负责 | 影响 | 下一步 |",
        "| --- | --- | --- | --- | --- |",
    ])
    for item in report.get("office", {}).get("capabilities", []):
        responsible = "".join(part for part in (item.get("owner_label", ""), item.get("model_kind", "")) if part)
        lines.append(_row(item.get("title"), item.get("status"), responsible, item.get("impact"), item.get("next_action")))

    lines.extend([
        "",
        "## 真实生产前检查",
        "",
        f"- 启动条件：{real.get('start_readiness_status') or real.get('status', '')}",
        f"- 启动说明：{real.get('summary', '')}",
        f"- 下一步：{real.get('next_action', '')}",
        f"- 完整制片包：{'可以开始' if real.get('can_start_full_production') else '暂不可以'}",
        f"- 故事/资产/提示词：{'可以先做' if real.get('can_start_limited_planning') else '暂不可以'}",
        f"- 真实产物证据：{real.get('verified_output_status', '')}",
        f"- 证据说明：{real.get('verified_output_summary', '')}",
        f"- 证据下一步：{real.get('verified_output_next_action', '')}",
        f"- 交付盘点：{inventory.get('manifest_count', 0)} 份；真实质量通过 {inventory.get('production_verified_count', 0)} 份；结构样例 {inventory.get('demo_only_count', 0)} 份",
        "",
        "| 检查项 | 状态 | 负责 | 下一步 |",
        "| --- | --- | --- | --- |",
    ])
    for item in real.get("required_capabilities", []):
        responsible = " / ".join(part for part in (item.get("owner_label", ""), item.get("model_kind", "")) if part)
        lines.append(_row(item.get("title"), item.get("status"), responsible, item.get("next_action") or item.get("impact")))

    checklist = real.get("operator_checklist") or []
    if checklist:
        lines.extend(["", "开工前清单："])
        lines.extend(f"- {item}" for item in checklist)

    promotion_gate = real.get("real_output_promotion_gate") or {}
    if promotion_gate:
        counts = promotion_gate.get("counts") or {}
        missing = "；".join(promotion_gate.get("missing_evidence") or []) or "无"
        lines.extend([
            "",
            "## 真实产物晋级卡",
            "",
            f"- 状态：{promotion_gate.get('status', '')}",
            f"- 是否可公开宣称真实质量：{'可以' if promotion_gate.get('can_promote_to_public_real_quality') else '不可以'}",
            f"- 判断：{promotion_gate.get('user_facing_decision', '')}",
            f"- 下一步：{promotion_gate.get('next_action', '')}",
            f"- 缺失证据：{missing}",
            f"- 盘点：manifest {counts.get('manifest_count', 0)} 份；真实质量通过 {counts.get('production_verified_count', 0)} 份；待修复 {counts.get('needs_review_count', 0)} 份；旧版不可审计 {counts.get('legacy_unverifiable_count', 0)} 份。",
            "",
            "| 验证 | 命令 | 证明什么 |",
            "| --- | --- | --- |",
        ])
        for item in promotion_gate.get("required_checks") or []:
            lines.append(_row(item.get("id"), item.get("command"), item.get("proves")))

    post_run = real.get("post_run_validation") or []
    if post_run:
        lines.extend([
            "",
            "## 真实生产后验收清单",
            "",
            "| 步骤 | 命令或动作 | 通过标准 | 失败处理 |",
            "| ---: | --- | --- | --- |",
        ])
        for item in post_run:
            lines.append(_row(
                item.get("step"),
                item.get("command") or item.get("title"),
                item.get("passes_when"),
                item.get("if_fails"),
            ))
    return "\n".join(lines)


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

