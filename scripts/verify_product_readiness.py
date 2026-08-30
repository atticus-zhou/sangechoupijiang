"""Verify product-level readiness gates for the real local product."""

from __future__ import annotations

import argparse
import json
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.product_readiness import audit_comic_production_readiness, format_readiness_markdown


def run_runtime_verification(root: Path) -> dict:
    """Run deterministic end-to-end verifiers without calling real providers."""
    from scripts.verify_comic_v2_delivery import verify_delivery
    from scripts.verify_comic_v2_user_flow import verify_user_flow

    fixture_path = root / "tests/fixtures/comic_v2_sample.json"
    with TemporaryDirectory(prefix="comic_readiness_") as tmp:
        temp_root = Path(tmp)
        delivery = verify_delivery(fixture_path, temp_root / "delivery")
        user_flow = verify_user_flow(fixture_path, temp_root / "user_flow")

    delivery_passed = bool(delivery.get("handoff_ready"))
    user_flow_passed = (
        user_flow.get("final_stage") == "ready_for_handoff"
        and bool(user_flow.get("delivery_audit", {}).get("handoff_ready"))
        and int(user_flow.get("download_bytes") or 0) > 0
    )
    delivery_result = {
        "status": "passed" if delivery_passed else "failed",
        "handoff_ready": delivery_passed,
        "asset_count": delivery.get("asset_count", 0),
        "shot_count": delivery.get("shot_count", 0),
        "embedded_images": delivery.get("embedded_images", 0),
        "handoff_manifest_exists": bool(delivery.get("handoff_manifest_exists")),
        "handoff_manifest_assets": delivery.get("handoff_manifest_assets", 0),
        "handoff_manifest_images": delivery.get("handoff_manifest_images", 0),
        "handoff_manifest_shots": delivery.get("handoff_manifest_shots", 0),
        "handoff_manifest_image_prompts": bool(delivery.get("handoff_manifest_image_prompts")),
        "handoff_manifest_prompt_strategy": bool(delivery.get("handoff_manifest_prompt_strategy")),
        "handoff_manifest_image_production_roles": bool(delivery.get("handoff_manifest_image_production_roles")),
        "handoff_manifest_asset_identity_fields": bool(delivery.get("handoff_manifest_asset_identity_fields")),
        "handoff_manifest_asset_baseline_chain": bool(delivery.get("handoff_manifest_asset_baseline_chain")),
        "handoff_manifest_shot_reference_images": bool(delivery.get("handoff_manifest_shot_reference_images")),
        "handoff_manifest_shot_execution_notes": bool(delivery.get("handoff_manifest_shot_execution_notes")),
        "handoff_manifest_shot_production_package": bool(delivery.get("handoff_manifest_shot_production_package")),
        "handoff_manifest_production_lineage": bool(delivery.get("handoff_manifest_production_lineage")),
        "handoff_manifest_lineage_handoff_fields": bool(delivery.get("handoff_manifest_lineage_handoff_fields")),
        "handoff_manifest_downstream_quick_start": bool(delivery.get("handoff_manifest_downstream_quick_start")),
        "handoff_manifest_downstream_quick_start_steps": delivery.get("handoff_manifest_downstream_quick_start_steps", 0),
        "word_canvas_agent_handoff": bool(delivery.get("word_canvas_agent_handoff")),
        "word_canvas_asset_file_references": bool(delivery.get("word_canvas_asset_file_references")),
        "missing_image_asset_ids": delivery.get("missing_image_asset_ids", []),
        "structural_errors": delivery.get("structural_errors", []),
    }
    user_flow_result = {
        "status": "passed" if user_flow_passed else "failed",
        "final_stage": user_flow.get("final_stage", ""),
        "visited_stages": user_flow.get("visited_stages", []),
        "visual_revisions": user_flow.get("visual_revisions", 0),
        "asset_revisions": user_flow.get("asset_revisions", 0),
        "handoff_manifest_asset_baseline_chain": bool(user_flow.get("handoff_manifest_asset_baseline_chain")),
        "handoff_manifest_shot_production_package": bool(user_flow.get("handoff_manifest_shot_production_package")),
        "production_lineage_handoff_fields": bool(user_flow.get("production_lineage_handoff_fields")),
        "generated_images": user_flow.get("generated_images", 0),
        "download_bytes": user_flow.get("download_bytes", 0),
        "artifact_count": user_flow.get("artifact_count", 0),
        "event_count": user_flow.get("event_count", 0),
    }
    return {
        "stage_b_product_loop": _stage_b_product_loop(root, delivery_result, user_flow_result),
        "delivery": delivery_result,
        "user_flow": user_flow_result,
    }


def _stage_b_product_loop(root: Path, delivery: dict, user_flow: dict) -> dict:
    """Summarize the Stage B comic-production product promises with evidence."""
    tasklist = (root / "docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8", errors="ignore")
    offices = (root / "src/offices.py").read_text(encoding="utf-8", errors="ignore")
    requirements = [
        {
            "id": "entry_modes",
            "title": "用户可从灵感、完整剧本、已有角色设定、参考风格进入工作流",
            "passed": all(marker in tasklist for marker in ("已有完整剧本", "已有角色设定", "已有参考风格")) and "完整剧本" in offices,
            "evidence": ["docs/PRODUCT_EVOLUTION_TASKLIST.md:4.1", "src/offices.py:input_types"],
        },
        {
            "id": "cabinet_boundary",
            "title": "内阁只负责故事对齐，三省六部负责生产拆解",
            "passed": "内阁只负责和人对齐故事" in tasklist and "中书省负责把确认故事变成生产合同" in tasklist,
            "evidence": ["docs/PRODUCT_EVOLUTION_TASKLIST.md:4.3"],
        },
        {
            "id": "multi_agent_outputs",
            "title": "三省六部产出故事合同、视觉母版、资产清单、镜头执行卡、提示词包和 Word 画布",
            "passed": bool(
                delivery.get("handoff_manifest_exists")
                and delivery.get("handoff_manifest_image_prompts")
                and delivery.get("handoff_manifest_prompt_strategy")
                and delivery.get("handoff_manifest_image_production_roles")
                and delivery.get("handoff_manifest_shot_production_package")
                and delivery.get("handoff_manifest_downstream_quick_start")
                and delivery.get("word_canvas_agent_handoff")
            ),
            "evidence": ["scripts/verify_comic_v2_delivery.py", "scripts/verify_comic_v2_user_flow.py"],
        },
        {
            "id": "revision_loop",
            "title": "用户能在关键节点退回，退回意见真实影响下一版结果",
            "passed": int(user_flow.get("visual_revisions") or 0) >= 1 and int(user_flow.get("asset_revisions") or 0) >= 1,
            "evidence": ["scripts/verify_comic_v2_user_flow.py:visual_revisions", "scripts/verify_comic_v2_user_flow.py:asset_revisions"],
        },
        {
            "id": "downstream_handoff",
            "title": "最终 Word 画布能被下游图片/视频工具理解",
            "passed": bool(
                delivery.get("handoff_ready")
                and delivery.get("word_canvas_asset_file_references")
                and delivery.get("handoff_manifest_shot_reference_images")
                and delivery.get("handoff_manifest_downstream_quick_start")
                and user_flow.get("final_stage") == "ready_for_handoff"
                and int(user_flow.get("download_bytes") or 0) > 1000
            ),
            "evidence": ["Word 制片画布", "handoff manifest", "shot production package"],
        },
    ]
    passed = all(item["passed"] for item in requirements)
    return {
        "status": "passed" if passed else "failed",
        "entry_modes_ready": requirements[0]["passed"],
        "cabinet_boundary_ready": requirements[1]["passed"],
        "multi_agent_outputs_ready": requirements[2]["passed"],
        "revision_loop_ready": requirements[3]["passed"],
        "downstream_handoff_ready": requirements[4]["passed"],
        "requirements": requirements,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format for the readiness audit.",
    )
    parser.add_argument(
        "--run-e2e",
        action="store_true",
        help="Run deterministic delivery and user-flow verifiers.",
    )
    args = parser.parse_args()

    audit = audit_comic_production_readiness(REPO_ROOT)
    if args.run_e2e:
        audit["runtime_verification"] = run_runtime_verification(REPO_ROOT)
        runtime_failed = any(
            item.get("status") != "passed"
            for item in audit["runtime_verification"].values()
        )
        if runtime_failed:
            audit["status"] = "needs_work"
            audit["summary"] = "AI 漫剧制片办公室静态条件存在，但运行时验证未全部通过。"
    if args.format == "markdown":
        print(format_readiness_markdown(audit))
    else:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit.get("status") in {"ready_without_demo", "ready_with_demo"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
