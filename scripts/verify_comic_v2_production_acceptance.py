"""Build one operator-facing acceptance card for the AI comic V2 package.

This verifier does not call model providers. It collects the existing no-key
delivery, downstream handoff, production benchmark, and public claim checks into
one decision that answers: can this package be shown, reproduced, or handed to a
downstream video workflow?
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

from scripts.verify_comic_real_production_claim import build_claim_report
from scripts.verify_comic_v2_downstream_handoff import verify_downstream_handoff
from scripts.verify_comic_v2_production_benchmark import verify_production_benchmark


DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "comic_v2_sample.json"
DEFAULT_OUTPUT = REPO_ROOT / "output" / "comic_v2_production_acceptance"


def verify_production_acceptance(
    fixture: Path = DEFAULT_FIXTURE,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    downstream = verify_downstream_handoff(
        Path(fixture),
        output_dir / "downstream_handoff",
    )
    benchmark = verify_production_benchmark(
        Path(fixture),
        output_dir / "production_benchmark",
    )
    claim = build_claim_report(output_dir=output_dir / "production_benchmark")

    prompt_summary = benchmark.get("prompt_quality_summary") or {}
    image_summary = benchmark.get("image_quality_summary") or {}
    real_gate = claim.get("real_quality_promotion_gate") or {}
    handoff_decision = claim.get("downstream_handoff_decision") or {}

    structure_ready = bool(downstream.get("downstream_handoff_ready"))
    prompts_ready = (
        prompt_summary.get("status") == "ready"
        and int(prompt_summary.get("issue_count") or 0) == 0
        and int(downstream.get("director_prompt_sets") or 0) == int(downstream.get("shot_count") or 0)
        and int(downstream.get("clean_asset_prompt_sets") or 0) == int(downstream.get("image_count") or 0)
    )
    assets_ready = (
        bool(downstream.get("asset_usage_map_ready"))
        and int(downstream.get("asset_image_requirement_missing") or 0) == 0
        and int(downstream.get("asset_image_requirement_ready") or 0)
        == int(downstream.get("asset_image_requirement_total") or 0)
        and int(downstream.get("clean_background_asset_images") or 0) > 0
    )
    delivery_ready = (
        bool(downstream.get("word_canvas_exists"))
        and bool(downstream.get("handoff_manifest_exists"))
        and int(downstream.get("quick_start_step_count") or 0) >= 5
    )
    real_quality_ready = bool(claim.get("can_claim_real_quality"))
    public_demo_safe = bool(claim.get("can_publicly_show")) and claim.get("claim_level") == "demo_structure_only"

    checklist = [
        {
            "id": "structure_handoff",
            "label": "结构化制片包可交接",
            "passed": structure_ready,
            "evidence": (
                f"assets={downstream.get('asset_count')}; "
                f"images={downstream.get('image_count')}; "
                f"shots={downstream.get('shot_count')}; "
                f"quick_start={downstream.get('quick_start_step_count')}"
            ),
        },
        {
            "id": "asset_identity_chain",
            "label": "资产身份证和引用链路完整",
            "passed": assets_ready,
            "evidence": (
                f"requirements={downstream.get('asset_image_requirement_ready')}/"
                f"{downstream.get('asset_image_requirement_total')}; "
                f"usage_map={downstream.get('asset_usage_map_referenced_assets')}/"
                f"{downstream.get('asset_count')}; "
                f"image_roles={downstream.get('asset_usage_map_image_roles')}"
            ),
        },
        {
            "id": "clean_base_assets",
            "label": "人物和道具基础资产保持干净背景",
            "passed": int(downstream.get("clean_background_asset_images") or 0) >= 4,
            "evidence": f"clean_background_asset_images={downstream.get('clean_background_asset_images')}",
        },
        {
            "id": "director_prompts",
            "label": "提示词具备导演执行信息",
            "passed": prompts_ready,
            "evidence": (
                f"asset_prompts={prompt_summary.get('clean_asset_prompt_count')}/"
                f"{prompt_summary.get('asset_prompt_count')}; "
                f"director_prompts={prompt_summary.get('director_prompt_count')}/"
                f"{prompt_summary.get('shot_prompt_count')}; "
                f"issues={prompt_summary.get('issue_count')}"
            ),
        },
        {
            "id": "word_canvas_and_manifest",
            "label": "Word 画布和 handoff manifest 可下载复核",
            "passed": delivery_ready,
            "evidence": (
                f"word_canvas={downstream.get('word_canvas')}; "
                f"manifest={downstream.get('handoff_manifest')}"
            ),
        },
        {
            "id": "real_quality_boundary",
            "label": "真实画质声明边界清楚",
            "passed": public_demo_safe or real_quality_ready,
            "evidence": (
                f"claim_level={claim.get('claim_level')}; "
                f"can_publicly_show={claim.get('can_publicly_show')}; "
                f"can_claim_real_quality={claim.get('can_claim_real_quality')}"
            ),
        },
    ]
    failed = [item for item in checklist if not item["passed"]]

    downstream_status = "ready_for_downstream" if real_quality_ready else "structure_demo_only"
    human_decision = (
        "这份包可以作为公开无 Key 样例展示流程、结构、引用链和 Word 画布；"
        "但当前仍是结构演示，不能说已经达到真实模型画质。"
    )
    if real_quality_ready:
        human_decision = "这份包已经具备真实生产质量证据，可以交给下游视频生成或剪辑流程继续使用。"
    if failed:
        downstream_status = "blocked"
        human_decision = "这份包还不能对外交接；先按失败项补齐资产、提示词、画布或声明证据。"

    return {
        "status": "passed" if not failed else "failed",
        "mode": "comic_v2_production_acceptance",
        "calls_real_models": False,
        "writes_workspace": True,
        "accepted_for_public_demo": public_demo_safe and not failed,
        "accepted_for_real_downstream": real_quality_ready and not failed,
        "downstream_status": downstream_status,
        "human_decision": human_decision,
        "operator_next_step": (
            "真实创作时，用真实 handoff manifest 重新运行生产基准和声明检查；"
            "只有 can_claim_real_quality=True 后才交给下游当成真实画质样例。"
        ),
        "checklist": checklist,
        "failure_count": len(failed),
        "failed_check_ids": [item["id"] for item in failed],
        "claim_level": claim.get("claim_level"),
        "quality_claim": benchmark.get("quality_claim"),
        "package_quality_score": benchmark.get("package_quality_score"),
        "production_quality_verified": benchmark.get("production_quality_verified"),
        "visual_evidence_level": benchmark.get("visual_evidence_level"),
        "image_quality_summary": {
            "total_images": image_summary.get("total_images", 0),
            "usable_images": image_summary.get("usable_images", 0),
            "waste_or_rework_images": image_summary.get("waste_or_rework_images", 0),
            "waste_or_rework_rate": image_summary.get("waste_or_rework_rate", 0),
        },
        "prompt_quality_summary": {
            "status": prompt_summary.get("status"),
            "issue_count": prompt_summary.get("issue_count", 0),
            "asset_prompt_count": prompt_summary.get("asset_prompt_count", 0),
            "clean_asset_prompt_count": prompt_summary.get("clean_asset_prompt_count", 0),
            "shot_prompt_count": prompt_summary.get("shot_prompt_count", 0),
            "director_prompt_count": prompt_summary.get("director_prompt_count", 0),
        },
        "downstream_handoff_decision": {
            "status": handoff_decision.get("status"),
            "handoff_allowed": handoff_decision.get("handoff_allowed"),
            "missing_before_handoff": handoff_decision.get("missing_before_handoff") or [],
        },
        "real_quality_promotion_gate": {
            "ready": real_gate.get("ready"),
            "status": real_gate.get("status"),
            "blocking_count": real_gate.get("blocking_count"),
            "next_action": real_gate.get("next_action"),
        },
        "evidence": {
            "word_canvas": downstream.get("word_canvas"),
            "handoff_manifest": downstream.get("handoff_manifest"),
            "asset_usage_map_items": downstream.get("asset_usage_map_items"),
            "asset_image_requirement_ready": downstream.get("asset_image_requirement_ready"),
            "asset_image_requirement_total": downstream.get("asset_image_requirement_total"),
            "structured_director_shots": downstream.get("structured_director_shots"),
            "quick_start_step_count": downstream.get("quick_start_step_count"),
        },
    }


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# AI Comic V2 Production Acceptance",
        "",
        f"Status: `{result.get('status')}`",
        f"Public demo accepted: `{result.get('accepted_for_public_demo')}`",
        f"Real downstream accepted: `{result.get('accepted_for_real_downstream')}`",
        f"Downstream status: `{result.get('downstream_status')}`",
        f"Claim level: `{result.get('claim_level')}`",
        f"Quality claim: `{result.get('quality_claim')}`",
        f"Production quality verified: `{result.get('production_quality_verified')}`",
        f"Visual evidence: `{result.get('visual_evidence_level')}`",
        "",
        "## Human Decision",
        "",
        str(result.get("human_decision") or ""),
        "",
        "## Acceptance Checklist",
        "",
        "| Check | Passed | Evidence |",
        "| --- | --- | --- |",
    ]
    for item in result.get("checklist") or []:
        lines.append(f"| {item.get('label')} | `{item.get('passed')}` | {item.get('evidence')} |")

    image = result.get("image_quality_summary") or {}
    prompt = result.get("prompt_quality_summary") or {}
    evidence = result.get("evidence") or {}
    gate = result.get("real_quality_promotion_gate") or {}
    lines.extend(
        [
            "",
            "## Evidence Summary",
            "",
            f"- Word canvas: `{evidence.get('word_canvas')}`",
            f"- Handoff manifest: `{evidence.get('handoff_manifest')}`",
            f"- Asset requirements: `{evidence.get('asset_image_requirement_ready')}/{evidence.get('asset_image_requirement_total')}`",
            f"- Asset usage map items: `{evidence.get('asset_usage_map_items')}`",
            f"- Structured director shots: `{evidence.get('structured_director_shots')}`",
            f"- Quick-start steps: `{evidence.get('quick_start_step_count')}`",
            f"- Images: `{image.get('usable_images')}/{image.get('total_images')} usable`, waste/rework `{image.get('waste_or_rework_images')}`",
            f"- Prompt quality: `{prompt.get('status')}`, issues `{prompt.get('issue_count')}`",
            f"- Real-quality gate: `{gate.get('status')}`, ready `{gate.get('ready')}`, blockers `{gate.get('blocking_count')}`",
            "",
            "## Next Step",
            "",
            str(result.get("operator_next_step") or ""),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build one acceptance card for AI comic V2 production.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="markdown")
    args = parser.parse_args()

    result = verify_production_acceptance(args.fixture, args.output_dir)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(format_markdown(result))
    else:
        print(
            "AI comic production acceptance: "
            f"{result['status']} "
            f"(public_demo={result.get('accepted_for_public_demo')}, "
            f"real_downstream={result.get('accepted_for_real_downstream')})"
        )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
