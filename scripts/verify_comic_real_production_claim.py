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

from scripts.verify_comic_v2_production_benchmark import verify_production_benchmark


def build_claim_report(manifest_path: Path | None = None) -> dict[str, Any]:
    benchmark = verify_production_benchmark(manifest_path=manifest_path)
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

    upgrade_checklist = _claim_upgrade_checklist(claim_level, benchmark)
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
        "claim_upgrade_checklist": upgrade_checklist,
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


def _claim_upgrade_checklist(claim_level: str, benchmark: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe the evidence needed before a stronger public quality claim is allowed."""
    visual_level = str(benchmark.get("visual_evidence_level") or "unknown")
    stored_matches = bool(benchmark.get("stored_benchmark_matches"))
    production_verified = bool(benchmark.get("production_quality_verified"))
    package_ready = bool(benchmark.get("package_quality_ready"))
    if claim_level == "real_quality_verified":
        return [
            {
                "id": "keep_evidence_bundle",
                "title": "保留真实质量证据包",
                "status": "complete",
                "required_evidence": ["handoff manifest", "Word 制片画布", "质量基准报告", "真实模型图片记录"],
                "why_it_matters": "后续公开展示、复盘或交给下游时，可以证明这不是 fixture 样例或口头声明。",
            },
            {
                "id": "repeat_after_major_edit",
                "title": "重大改动后重新验证",
                "status": "required_when_changed",
                "required_evidence": ["新的 manifest", "新的质量基准", "新的真实生产声明报告"],
                "why_it_matters": "故事、资产、模型或提示词变更后，旧质量声明不能自动继承。",
            },
        ]
    if claim_level == "demo_structure_only":
        return [
            {
                "id": "run_real_models",
                "title": "使用真实模型生成图片资产",
                "status": "missing",
                "required_evidence": ["非 fixture 图片", "provider", "model", "image_id", "生成时间或生产记录"],
                "why_it_matters": "固定样例只能证明结构，不能证明真实模型画风、人物一致性或资产可用性。",
            },
            {
                "id": "visual_review",
                "title": "执行真实视觉质检",
                "status": "missing" if visual_level != "model_reviewed" else "complete",
                "required_evidence": ["review.status=pass", "handoff_ready=true", "fixture=false", "各维度分数"],
                "why_it_matters": "只有视觉质检通过，才能把人物、道具、场景和画风一致性作为公开质量证据。",
            },
            {
                "id": "stored_benchmark",
                "title": "重新写入并复核质量基准",
                "status": "complete" if stored_matches else "missing",
                "required_evidence": ["quality_benchmark", "stored_benchmark_matches=true", "production_quality_verified=true"],
                "why_it_matters": "公开声明必须来自当前 manifest 的机器可复核基准，而不是人工口头判断。",
            },
        ]
    recovery = benchmark.get("recommended_recovery") or {}
    return [
        {
            "id": "resolve_blockers",
            "title": "先处理阻塞项",
            "status": "missing",
            "required_evidence": ["quality_benchmark.issues", "recommended_recovery", "责任部门修复记录"],
            "why_it_matters": "存在 blocker 时，制片包不能当成可交付材料，也不能进入真实质量声明。",
        },
        {
            "id": "rerun_benchmark",
            "title": "修复后重跑质量基准",
            "status": "missing" if not package_ready else "partial",
            "required_evidence": ["package_quality_ready=true", "blocker_count=0", "新的 claim report"],
            "why_it_matters": str(
                recovery.get("description")
                or benchmark.get("next_action")
                or "需要用新的质量基准证明阻塞项已经处理。"
            ),
        },
        {
            "id": "upgrade_visual_evidence",
            "title": "补齐真实视觉证据",
            "status": "missing" if not production_verified else "complete",
            "required_evidence": ["model_reviewed 图片", "视觉质检通过", "production_quality_verified=true"],
            "why_it_matters": "即使结构修好，没有真实视觉证据也不能宣称真实模型画质通过。",
        },
    ]


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
    lines.extend(["", "## Next Action", "", str(report.get("next_action") or "")])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build an honest claim report for an AI comic handoff.")
    parser.add_argument("--manifest", type=Path, help="Existing handoff manifest to audit.")
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="markdown")
    args = parser.parse_args()

    report = build_claim_report(args.manifest)
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
