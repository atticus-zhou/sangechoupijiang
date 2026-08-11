"""Build an honest public claim report for an AI comic production handoff.

This script never calls model providers. It audits an existing handoff manifest,
or the deterministic no-key fixture when no manifest is supplied, and converts
the benchmark result into language a product operator can safely use in a
portfolio, README, demo page, or downstream handoff.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_comic_v2_production_benchmark import DEFAULT_OUTPUT, verify_production_benchmark
from src.comic_office.v2.claim_report import (
    claim_upgrade_checklist,
    claim_upgrade_recovery,
    downstream_handoff_decision_card,
    real_quality_promotion_gate,
)


def build_claim_report(manifest_path: Path | None = None, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    benchmark = verify_production_benchmark(manifest_path=manifest_path, output_dir=output_dir)
    claim = str(benchmark.get("quality_claim") or "")
    production_verified = bool(benchmark.get("production_quality_verified"))
    package_ready = bool(benchmark.get("package_quality_ready"))
    stored_matches = bool(benchmark.get("stored_benchmark_matches"))
    can_publicly_show = claim in {"production_quality_verified", "demo_structure_verified"} and stored_matches

    if production_verified:
        claim_level = "real_quality_verified"
        allowed_claims = [
            "这份制片包已通过真实模型产物质量基准。",
            "可以展示人物、道具、场景、镜头提示词、Word 画布和引用链路。",
            "可以交给下游图生视频、剪辑或制片执行流程继续使用。",
        ]
        forbidden_claims = [
            "不能说系统已经自动生成完整成片。",
            "不能承诺所有第三方视频平台都会一次生成成功。",
        ]
        next_action = "保留 manifest、Word 画布和质量报告，一起作为真实交付证据展示。"
        downstream_status = "ready_for_downstream"
    elif claim == "demo_structure_verified" and package_ready:
        claim_level = "demo_structure_only"
        allowed_claims = [
            "这份无 Key 样例证明流程、引用链和交付结构可复现。",
            "可以展示 Word 制片画布、handoff manifest 和下游交接方式。",
            "可以作为面试官或访客理解产品能力的固定样例。",
        ]
        forbidden_claims = [
            "不能宣称真实模型画质已验证。",
            "不能宣称人物一致性、画风一致性已经通过真实生产检验。",
            "不能把占位图或 fixture 图说成真实创作成品。",
        ]
        next_action = "真实创作完成后，用该脚本指向真实 handoff manifest 重新生成声明报告。"
        downstream_status = "structure_demo_only"
    else:
        claim_level = "needs_review"
        recovery = benchmark.get("recommended_recovery") or {}
        allowed_claims = [
            "这份制片包只能作为内部草稿或问题复盘材料。",
            "可以展示阻塞原因、责任部门和恢复动作。",
        ]
        forbidden_claims = [
            "不能公开宣称该制片包已经可交付。",
            "不能交给下游平台当成最终制片材料。",
            "不能隐藏质量基准中的 blocker 或恢复建议。",
        ]
        next_action = str(
            recovery.get("description")
            or benchmark.get("next_action")
            or "先处理质量基准中的阻塞项，再重新生成声明报告。"
        )
        downstream_status = "blocked"

    upgrade_checklist = claim_upgrade_checklist(claim_level, benchmark)
    upgrade_recovery = claim_upgrade_recovery(claim_level, benchmark)
    promotion_gate = real_quality_promotion_gate(benchmark)
    handoff_decision = downstream_handoff_decision_card(claim_level, benchmark)
    return {
        "status": "passed",
        "mode": "comic_real_production_claim",
        "calls_real_models": False,
        "writes_workspace": manifest_path is None,
        "claim_level": claim_level,
        "quality_claim": claim,
        "can_publicly_show": can_publicly_show,
        "can_claim_real_quality": production_verified and stored_matches,
        "downstream_status": downstream_status,
        "allowed_public_claims": allowed_claims,
        "forbidden_public_claims": forbidden_claims,
        "real_quality_promotion_gate": promotion_gate,
        "downstream_handoff_decision": handoff_decision,
        "real_model_evidence_requirements": benchmark.get("real_model_evidence_requirements") or {},
        "claim_upgrade_checklist": upgrade_checklist,
        "claim_upgrade_recovery": upgrade_recovery,
        "next_action": next_action,
        "evidence": {
            "manifest_path": benchmark.get("manifest_path", ""),
            "word_canvas": benchmark.get("word_canvas", ""),
            "package_quality_score": benchmark.get("package_quality_score"),
            "visual_evidence_level": benchmark.get("visual_evidence_level"),
            "stored_benchmark_matches": stored_matches,
            "production_quality_verified": production_verified,
        },
        "benchmark": benchmark,
    }


def format_markdown(report: dict[str, Any]) -> str:
    evidence = report.get("evidence") or {}
    lines = [
        "# AI Comic Real Production Claim",
        "",
        f"Status: `{report.get('status')}`",
        f"Claim level: `{report.get('claim_level')}`",
        f"Quality claim: `{report.get('quality_claim')}`",
        f"Can publicly show: `{report.get('can_publicly_show')}`",
        f"Can claim real quality: `{report.get('can_claim_real_quality')}`",
        f"Downstream status: `{report.get('downstream_status')}`",
        f"Calls real models: `{report.get('calls_real_models')}`",
        "",
        "## Evidence",
        "",
        f"- Manifest: `{evidence.get('manifest_path')}`",
        f"- Word canvas: `{evidence.get('word_canvas')}`",
        f"- Score: `{evidence.get('package_quality_score')}`",
        f"- Visual evidence: `{evidence.get('visual_evidence_level')}`",
        f"- Stored benchmark matches: `{evidence.get('stored_benchmark_matches')}`",
        "",
        "## Allowed Public Claims",
        "",
    ]
    lines.extend(f"- {item}" for item in report.get("allowed_public_claims", []))
    lines.extend(["", "## Forbidden Public Claims", ""])
    lines.extend(f"- {item}" for item in report.get("forbidden_public_claims", []))
    promotion_gate = report.get("real_quality_promotion_gate") or {}
    lines.extend(
        [
            "",
            "## Real Quality Promotion Gate",
            "",
            f"- Ready: `{promotion_gate.get('ready')}`",
            f"- Status: `{promotion_gate.get('status')}`",
            f"- Blocking checks: `{promotion_gate.get('blocking_count')}`",
            f"- Next action: {promotion_gate.get('next_action')}",
            "",
            "| Check | Passed | Evidence | If Missing |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in promotion_gate.get("checks") or []:
        lines.append(
            f"| {item.get('label')} | `{item.get('passed')}` | {item.get('evidence')} | {item.get('if_missing')} |"
        )
    real_model_evidence = report.get("real_model_evidence_requirements") or {}
    if real_model_evidence:
        lines.extend(
            [
                "",
                "## Real Model Evidence Requirements",
                "",
                f"- Status: `{real_model_evidence.get('status')}`",
                f"- Ready for real quality claim: `{real_model_evidence.get('ready_for_real_quality_claim')}`",
                f"- Visual evidence level: `{real_model_evidence.get('visual_evidence_level')}`",
                f"- Missing checks: `{', '.join(real_model_evidence.get('missing_check_ids') or []) or 'none'}`",
                f"- Next action: {real_model_evidence.get('next_action')}",
                "",
                "| Check | Passed | Evidence | If Missing |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in real_model_evidence.get("checks") or []:
            lines.append(
                f"| {item.get('id')} | `{item.get('passed')}` | {item.get('evidence')} | {item.get('if_missing')} |"
            )
    decision = report.get("downstream_handoff_decision") or {}
    lines.extend(
        [
            "",
            "## Downstream Handoff Decision",
            "",
            f"- Status: `{decision.get('status')}`",
            f"- Handoff allowed: `{decision.get('handoff_allowed')}`",
            f"- Decision: {decision.get('decision')}",
            f"- Human message: {decision.get('human_message')}",
            f"- Operator next step: {decision.get('operator_next_step')}",
            "",
            "### Missing Before Handoff",
            "",
        ]
    )
    missing = [str(item) for item in (decision.get("missing_before_handoff") or []) if str(item).strip()]
    lines.extend(f"- {item}" for item in (missing or ["none"]))
    lines.extend(["", "### Required Actions", ""])
    actions = [str(item) for item in (decision.get("required_actions") or []) if str(item).strip()]
    lines.extend(f"- {item}" for item in (actions or ["none"]))
    lines.extend(["", "### Decision Evidence", ""])
    evidence_items = [str(item) for item in (decision.get("evidence") or []) if str(item).strip()]
    lines.extend(f"- {item}" for item in (evidence_items or ["none"]))
    lines.extend(["", "## Claim Upgrade Checklist", ""])
    for item in report.get("claim_upgrade_checklist", []):
        evidence = ", ".join(item.get("required_evidence") or [])
        lines.extend(
            [
                f"### {item.get('title')}",
                "",
                f"- Status: `{item.get('status')}`",
                f"- Required evidence: {evidence}",
                f"- Why it matters: {item.get('why_it_matters')}",
                "",
            ]
        )
    recovery = report.get("claim_upgrade_recovery") or {}
    lines.extend(
        [
            "",
            "## Claim Upgrade Recovery",
            "",
            f"- Required: `{recovery.get('required')}`",
            f"- Recovery action: `{recovery.get('recovery_action')}`",
            f"- Recovery endpoint: `{recovery.get('recovery_endpoint')}`",
            f"- Reason: {recovery.get('reason')}",
            f"- Next action: {recovery.get('next_action')}",
            f"- Preserves: {', '.join(recovery.get('preserves') or [])}",
            f"- Rebuilds: {', '.join(recovery.get('rebuilds') or [])}",
            "",
            "### Steps",
            "",
        ]
    )
    for step in recovery.get("steps") or []:
        lines.extend(
            [
                f"{step.get('order')}. **{step.get('owner')}**: {step.get('action')}",
                f"   - Evidence: {step.get('evidence')}",
                f"   - Expected: {step.get('expected')}",
            ]
        )
    lines.extend(["", "## Next Action", "", str(report.get("next_action") or "")])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build an honest claim report for an AI comic handoff.")
    parser.add_argument("--manifest", type=Path, help="Existing handoff manifest to audit.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="markdown")
    args = parser.parse_args()

    report = build_claim_report(args.manifest, output_dir=args.output_dir)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(format_markdown(report))
    else:
        print(
            "AI comic claim report: "
            f"{report['claim_level']} "
            f"(real_quality={report['can_claim_real_quality']}, "
            f"downstream={report['downstream_status']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
