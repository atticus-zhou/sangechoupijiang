"""Verify the AI comic real-run evidence intake contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_comic_real_production_claim import build_claim_report
from scripts.verify_comic_v2_downstream_handoff import verify_downstream_handoff
from scripts.verify_comic_v2_production_benchmark import verify_production_benchmark

DOC_PATH = REPO_ROOT / "docs" / "COMIC_REAL_RUN_EVIDENCE_INTAKE.md"
INTAKE_OUTPUT_ROOT = REPO_ROOT / "output" / "comic_real_run_evidence_intake"

REQUIRED_MARKERS = [
    "AI 漫剧真实运行证据收口单",
    "demo_structure_only",
    "real_quality_verified",
    "office_id=comic_production",
    "model_evidence",
    "image_production_evidence",
    "image_quality_summary",
    "waste_or_rework_images",
    "failed_image_ids",
    "rework_instructions",
    "asset_identity_cards",
    "reference_asset_chain",
    "prompt_strategy_lineage",
    "downstream_handoff_decision",
    "人物三视图",
    "人物表情表",
    "干净白底",
    "广角图",
    "俯视图",
    "首帧参考图",
    "负面提示词",
    "禁止",
    "Word 制片画布",
    "regenerate_images",
    "python scripts/verify_comic_real_production_claim.py --format markdown",
    "python scripts/verify_comic_v2_production_benchmark.py --format markdown",
    "python scripts/verify_comic_v2_downstream_handoff.py --format markdown",
    "python scripts/verify_release_readiness.py --format markdown",
]

EXPECTED_HUMAN_FLOW = [
    "用户确认完整故事",
    "中书省和门下省完成资产拆解",
    "工部开始生成基础资产图和镜头参考图",
    "刑部逐张做视觉质检",
    "兵部生成导演式提示词",
    "礼部组装 Word 制片画布",
]

EXPECTED_RECOVERY_ACTIONS = [
    "regenerate_images",
    "退回中书省和门下省",
    "退回兵部",
    "退回礼部",
]


def _read_doc() -> tuple[str, str | None]:
    if not DOC_PATH.exists():
        return "", "missing"
    try:
        return DOC_PATH.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as exc:
        return "", f"utf8_decode_error:{exc}"


def verify_real_run_evidence_intake(manifest_path: Path | None = None) -> dict[str, Any]:
    text, read_error = _read_doc()
    benchmark = verify_production_benchmark(output_dir=INTAKE_OUTPUT_ROOT / "benchmark", manifest_path=manifest_path)
    claim = build_claim_report(manifest_path=manifest_path, output_dir=INTAKE_OUTPUT_ROOT / "claim")
    handoff = verify_downstream_handoff(output_dir=INTAKE_OUTPUT_ROOT / "handoff", manifest_path=manifest_path)

    errors: list[str] = []
    missing_markers = [marker for marker in REQUIRED_MARKERS if marker not in text]
    missing_flow = [marker for marker in EXPECTED_HUMAN_FLOW if marker not in text]
    missing_recovery = [marker for marker in EXPECTED_RECOVERY_ACTIONS if marker not in text]

    if read_error:
        errors.append(f"real-run evidence intake doc read error: {read_error}")
    if missing_markers:
        errors.append(f"real-run evidence intake doc missing markers: {', '.join(missing_markers)}")
    if missing_flow:
        errors.append(f"real-run evidence intake doc missing human flow markers: {', '.join(missing_flow)}")
    if missing_recovery:
        errors.append(f"real-run evidence intake doc missing recovery markers: {', '.join(missing_recovery)}")

    if benchmark.get("status") != "passed":
        errors.append("comic production benchmark verifier must pass")
    if claim.get("status") != "passed":
        errors.append("comic real production claim verifier must pass")
    if handoff.get("status") != "passed":
        errors.append("comic downstream handoff verifier must pass")

    auditing_fixed_sample = manifest_path is None
    if auditing_fixed_sample and benchmark.get("production_quality_verified") is not False:
        errors.append("fixed public sample must stay non-production until real model evidence is present")
    if auditing_fixed_sample and claim.get("claim_level") != "demo_structure_only":
        errors.append("fixed public sample claim level must stay demo_structure_only")
    if auditing_fixed_sample and claim.get("can_claim_real_quality") is not False:
        errors.append("fixed public sample must not claim real quality")
    claim_decision = claim.get("downstream_handoff_decision") or {}
    if auditing_fixed_sample and claim_decision.get("status") != "structure_demo_only":
        errors.append("fixed public sample downstream claim decision must stay structure_demo_only")
    if auditing_fixed_sample and claim_decision.get("handoff_allowed") is not False:
        errors.append("fixed public sample must not allow real downstream handoff")
    if handoff.get("downstream_handoff_ready") is not True:
        errors.append("comic handoff must stay structurally reproducible")

    text_sections = {
        "evidence": all(marker in text for marker in ("model_evidence", "image_production_evidence", "prompt_strategy_lineage")),
        "asset_quality": all(marker in text for marker in ("人物三视图", "人物表情表", "干净白底", "广角图", "俯视图")),
        "prompt_quality": all(marker in text for marker in ("镜头目的", "参考链路", "摄影计划", "人物表演", "负面提示词")),
        "word_canvas": all(marker in text for marker in ("故事合同", "资产身份证", "图片联系表", "镜头卡", "提示词包")),
        "recovery": not missing_recovery,
        "public_claim": all(marker in text for marker in ("production_quality_verified=true", "handoff_allowed=true")),
    }

    return {
        "status": "passed" if not errors else "failed",
        "mode": "comic_real_run_evidence_intake",
        "audited_manifest": str(manifest_path) if manifest_path else "",
        "audit_subject": "existing_manifest" if manifest_path else "fixed_public_sample",
        "summary": (
            "AI comic real-run evidence intake is documented and bound to production claim, benchmark, and downstream gates."
            if not errors
            else "AI comic real-run evidence intake has gaps."
        ),
        "document": "docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md",
        "line_count": len(text.splitlines()) if text else 0,
        "missing_marker_count": len(missing_markers),
        "human_flow_step_count": len(EXPECTED_HUMAN_FLOW) - len(missing_flow),
        "recovery_action_count": len(EXPECTED_RECOVERY_ACTIONS) - len(missing_recovery),
        "section_status": text_sections,
        "benchmark_claim": benchmark.get("quality_claim"),
        "benchmark_real_quality_verified": benchmark.get("production_quality_verified"),
        "claim_level": claim.get("claim_level"),
        "can_claim_real_quality": claim.get("can_claim_real_quality"),
        "downstream_status": claim_decision.get("status"),
        "handoff_allowed": claim_decision.get("handoff_allowed"),
        "real_quality_promotion_ready": (claim.get("real_quality_promotion_gate") or {}).get("ready"),
        "visual_evidence_level": benchmark.get("visual_evidence_level"),
        "image_quality_summary": benchmark.get("image_quality_summary") or {},
        "prompt_strategy_lineage": benchmark.get("prompt_strategy_lineage") or {},
        "real_model_evidence_requirements": benchmark.get("real_model_evidence_requirements") or {},
        "structural_downstream_handoff_ready": handoff.get("downstream_handoff_ready"),
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    sections = payload.get("section_status") or {}
    lines = [
        "# AI Comic Real-Run Evidence Intake Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Audit subject: `{payload.get('audit_subject')}`",
        f"Summary: {payload.get('summary')}",
        "",
        f"- Document: `{payload.get('document')}`",
        f"- Audited manifest: `{payload.get('audited_manifest') or 'generated fixture'}`",
        f"- Lines: `{payload.get('line_count')}`",
        f"- Missing markers: `{payload.get('missing_marker_count')}`",
        f"- Human flow steps: `{payload.get('human_flow_step_count')}`",
        f"- Recovery actions: `{payload.get('recovery_action_count')}`",
        f"- Benchmark: `{payload.get('benchmark_claim')}` / real_quality={payload.get('benchmark_real_quality_verified')}",
        f"- Public claim: `{payload.get('claim_level')}` / can_claim_real_quality={payload.get('can_claim_real_quality')}",
        f"- Downstream: `{payload.get('downstream_status')}` / handoff_allowed={payload.get('handoff_allowed')}",
        f"- Real quality promotion ready: `{payload.get('real_quality_promotion_ready')}`",
        f"- Visual evidence: `{payload.get('visual_evidence_level')}`",
        f"- Structural handoff reproducible: `{payload.get('structural_downstream_handoff_ready')}`",
        "",
        "## Sections",
        "",
    ]
    lines.extend(f"- {name}: `{status}`" for name, status in sections.items())
    image_summary = payload.get("image_quality_summary") or {}
    if image_summary:
        lines.extend([
            "",
            "## Image Evidence",
            "",
            f"- Total images: `{image_summary.get('total_images', 0)}`",
            f"- Usable images: `{image_summary.get('usable_images', 0)}`",
            f"- Waste/rework images: `{image_summary.get('waste_or_rework_images', 0)}`",
            f"- Failed image ids: `{', '.join(image_summary.get('failed_image_ids') or []) or 'none'}`",
        ])
    evidence = payload.get("real_model_evidence_requirements") or {}
    if evidence:
        lines.extend([
            "",
            "## Real Model Evidence",
            "",
            f"- Status: `{evidence.get('status')}`",
            f"- Ready for real quality claim: `{evidence.get('ready_for_real_quality_claim')}`",
            f"- Missing checks: `{', '.join(evidence.get('missing_check_ids') or []) or 'none'}`",
            f"- Next action: {evidence.get('next_action')}",
        ])
    strategy = payload.get("prompt_strategy_lineage") or {}
    if strategy:
        lines.extend([
            "",
            "## Prompt Strategy Lineage",
            "",
            f"- Status: `{strategy.get('status')}`",
            f"- Expected version: `{strategy.get('expected_prompt_strategy_version')}`",
            f"- Package version: `{strategy.get('package_prompt_strategy_version')}`",
            f"- Missing checks: `{', '.join(strategy.get('missing_check_ids') or []) or 'none'}`",
        ])
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="Existing comic V2 handoff manifest to audit.")
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()
    payload = verify_real_run_evidence_intake(manifest_path=args.manifest)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
