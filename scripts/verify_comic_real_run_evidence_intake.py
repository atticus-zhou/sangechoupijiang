"""Verify the AI comic real-run evidence intake contract."""

from __future__ import annotations

import argparse
import json
import re
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
TEMPLATE_PATH = REPO_ROOT / "docs" / "COMIC_REAL_RUN_EVIDENCE_TEMPLATE.json"
INTAKE_OUTPUT_ROOT = REPO_ROOT / "output" / "comic_real_run_evidence_intake"
DEFAULT_USER_OUTPUT_ROOT = REPO_ROOT / "output" / "workspaces"

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
    "prompt_director_contract",
    "operator_acceptance_checklist",
    "recovery_protocol",
    "downstream_handoff_decision",
    "人物三视图",
    "人物表情表",
    "干净白底",
    "广角图",
    "俯视图",
    "首帧参考图",
    "负面提示词",
    "禁止",
    "prompt_director_contract",
    "shot_purpose",
    "reference_image_chain",
    "camera_plan",
    "performance_direction",
    "continuity_constraints",
    "Word 制片画布",
    "regenerate_images",
    "recovery_protocol",
    "return_to_stage",
    "operator_next_step",
    "python scripts/verify_comic_real_production_claim.py --format markdown",
    "python scripts/verify_comic_v2_production_benchmark.py --format markdown",
    "python scripts/verify_comic_v2_downstream_handoff.py --format markdown",
    "python scripts/verify_release_readiness.py --format markdown",
    "docs/COMIC_REAL_RUN_EVIDENCE_TEMPLATE.json",
    "证据导入模板",
    "人工验收签字",
    "--evidence-file",
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

TEMPLATE_REQUIRED_TOP_LEVEL = [
    "schema",
    "office_id",
    "claim_boundary",
    "workspace",
    "model_evidence",
    "generated_images",
    "visual_reviews",
    "image_quality_summary",
    "asset_identity_cards",
    "reference_asset_chain",
    "prompt_strategy_lineage",
    "prompt_director_contract",
    "operator_acceptance_checklist",
    "recovery_protocol",
    "delivery_files",
    "downstream_handoff_decision",
]

TEMPLATE_FORBIDDEN_MARKERS = [
    "api_key",
    "cookie",
    "browser_profile",
    "config.yaml",
    ".env",
    "user_data",
    "raw_provider_secret",
]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _placeholder_paths(payload: Any, path: str = "$") -> list[str]:
    placeholders: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            placeholders.extend(_placeholder_paths(value, f"{path}.{key}"))
        return placeholders
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            placeholders.extend(_placeholder_paths(value, f"{path}[{index}]"))
        return placeholders
    if isinstance(payload, str):
        lowered = payload.lower()
        if "replace_" in lowered or "_replace" in lowered or "ws_xxx" in lowered or "2026-01-01t00:00:00z" in lowered:
            placeholders.append(path)
    return placeholders


def _verify_template_contract(path: Path = TEMPLATE_PATH, *, strict_real_values: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    try:
        template = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "status": "failed",
            "path": _display_path(path),
            "errors": ["real-run evidence intake template is missing"],
        }
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "failed",
            "path": _display_path(path),
            "errors": [f"real-run evidence intake template is not valid JSON: {exc}"],
        }
    if not isinstance(template, dict):
        return {
            "status": "failed",
            "path": _display_path(path),
            "errors": ["real-run evidence intake template must be a JSON object"],
        }

    missing = [field for field in TEMPLATE_REQUIRED_TOP_LEVEL if field not in template]
    if missing:
        errors.append(f"template missing top-level fields: {', '.join(missing)}")
    if template.get("schema") != "comic_real_run_evidence_intake_v1":
        errors.append("template schema must be comic_real_run_evidence_intake_v1")
    if template.get("office_id") != "comic_production":
        errors.append("template office_id must be comic_production")
    if strict_real_values:
        placeholder_fields = _placeholder_paths(template)
        if placeholder_fields:
            errors.append(
                "evidence file still contains placeholder values: "
                + ", ".join(placeholder_fields[:12])
                + (" ..." if len(placeholder_fields) > 12 else "")
            )

    claim_boundary = template.get("claim_boundary") or {}
    must_not_include = claim_boundary.get("must_not_include") or []
    for marker in TEMPLATE_FORBIDDEN_MARKERS:
        if marker not in must_not_include:
            errors.append(f"template claim_boundary.must_not_include must list {marker}")
    if "downstream_handoff_allowed" not in (claim_boundary.get("public_claim_allowed_only_after") or []):
        errors.append("template must require downstream_handoff_allowed before public real-quality claims")

    model_evidence = template.get("model_evidence") or {}
    for department in ("gongbu_image_generation", "xingbu_visual_review", "bingbu_prompt_director"):
        evidence = model_evidence.get(department) or {}
        if not all(evidence.get(field) for field in ("provider", "model", "request_trace_ids")):
            errors.append(f"template model_evidence.{department} must include provider, model, and request_trace_ids")

    generated_images = template.get("generated_images") or []
    if not generated_images:
        errors.append("template generated_images must include at least one image record")
    generated_image_ids: set[str] = set()
    image_roles_by_asset: dict[str, set[str]] = {}
    for index, image in enumerate(generated_images):
        required = (
            "image_id",
            "production_role",
            "file_path",
            "provider",
            "model",
            "fixture",
            "prompt_hash",
            "file_sha256",
            "byte_size",
            "dimensions",
        )
        missing_image = [field for field in required if field not in image]
        if missing_image:
            errors.append(f"template generated_images[{index}] missing fields: {', '.join(missing_image)}")
        if image.get("fixture") is not False:
            errors.append(f"template generated_images[{index}].fixture must be false")
        if not (image.get("asset_id") or image.get("shot_id")):
            errors.append(f"template generated_images[{index}] must bind to asset_id or shot_id")
        sha256 = str(image.get("file_sha256") or "")
        if not sha256:
            errors.append(f"template generated_images[{index}].file_sha256 must be present")
        if strict_real_values and not re.fullmatch(r"[a-fA-F0-9]{64}", sha256):
            errors.append(f"evidence file generated_images[{index}].file_sha256 must be a 64-character hex digest")
        byte_size = image.get("byte_size")
        if not isinstance(byte_size, int) or byte_size <= 0:
            errors.append(f"template generated_images[{index}].byte_size must be a positive integer")
        dimensions = image.get("dimensions") or {}
        width = dimensions.get("width") if isinstance(dimensions, dict) else None
        height = dimensions.get("height") if isinstance(dimensions, dict) else None
        if not isinstance(width, int) or width <= 0 or not isinstance(height, int) or height <= 0:
            errors.append(f"template generated_images[{index}].dimensions must include positive integer width and height")
        image_id = str(image.get("image_id") or "")
        if image_id:
            generated_image_ids.add(image_id)
        asset_id = str(image.get("asset_id") or "")
        if asset_id:
            image_roles_by_asset.setdefault(asset_id, set()).add(str(image.get("production_role") or ""))

    reviews = template.get("visual_reviews") or []
    if not reviews:
        errors.append("template visual_reviews must include at least one review record")
    reviewed_image_ids: set[str] = set()
    for index, review in enumerate(reviews):
        image_id = str(review.get("image_id") or "")
        if image_id:
            reviewed_image_ids.add(image_id)
        if image_id and image_id not in generated_image_ids:
            errors.append(f"template visual_reviews[{index}] points to unknown image_id")
        if review.get("reviewer_department") != "xingbu":
            errors.append(f"template visual_reviews[{index}] must be owned by xingbu")
        scores = review.get("scores") or {}
        if len(scores) < 7:
            errors.append(f"template visual_reviews[{index}] must include seven-dimensional scores")
        if review.get("status") not in {"pass", "needs_review", "fail"}:
            errors.append(f"template visual_reviews[{index}].status must be pass, needs_review, or fail")
    missing_reviews = sorted(generated_image_ids - reviewed_image_ids)
    if missing_reviews:
        errors.append("template visual_reviews must cover every generated image: " + ", ".join(missing_reviews))

    summary = template.get("image_quality_summary") or {}
    for field in ("total_images", "usable_images", "waste_or_rework_images", "failed_image_ids", "rework_instructions"):
        if field not in summary:
            errors.append(f"template image_quality_summary must include {field}")
    if strict_real_values and generated_images:
        if summary.get("total_images") != len(generated_images):
            errors.append("evidence file image_quality_summary.total_images must match generated_images")
        pass_reviews = [
            review
            for review in reviews
            if review.get("status") == "pass"
        ]
        if summary.get("usable_images") != len(pass_reviews):
            errors.append("evidence file image_quality_summary.usable_images must match pass visual reviews")

    asset_cards = template.get("asset_identity_cards") or []
    if not asset_cards:
        errors.append("template asset_identity_cards must include at least one approved asset card")
    asset_types_present = {
        str(card.get("asset_type") or "")
        for card in asset_cards
        if card.get("asset_type")
    }
    missing_asset_types = sorted({"character", "prop", "scene"} - asset_types_present)
    if missing_asset_types:
        errors.append("template asset_identity_cards must include asset types: " + ", ".join(missing_asset_types))
    for index, card in enumerate(asset_cards):
        required = (
            "asset_id",
            "asset_type",
            "name",
            "story_source",
            "identity_baseline_image_id",
            "required_image_kinds",
            "approved_image_ids",
            "continuity_locks",
            "human_review_status",
        )
        missing_card = [field for field in required if field not in card]
        if missing_card:
            errors.append(f"template asset_identity_cards[{index}] missing fields: {', '.join(missing_card)}")
        if card.get("asset_type") not in {"character", "prop", "scene"}:
            errors.append(f"template asset_identity_cards[{index}].asset_type must be character, prop, or scene")
        asset_id = str(card.get("asset_id") or "")
        asset_type = str(card.get("asset_type") or "")
        roles = image_roles_by_asset.get(asset_id, set())
        if asset_type == "character" and "clean_character_identity_three_view" not in roles:
            errors.append(f"template asset_identity_cards[{index}] character must have clean_character_identity_three_view")
        if asset_type == "prop" and "clean_prop_turnaround_reference" not in roles:
            errors.append(f"template asset_identity_cards[{index}] prop must have clean_prop_turnaround_reference")
        if asset_type == "scene":
            for role in ("scene_wide_establishing", "scene_top_down_layout"):
                if role not in roles:
                    errors.append(f"template asset_identity_cards[{index}] scene must have {role}")
        if asset_type in {"character", "prop"} and card.get("clean_background_required") is not True:
            errors.append(f"template asset_identity_cards[{index}] {asset_type} must require a clean background")
        if not card.get("identity_baseline_image_id"):
            errors.append(f"template asset_identity_cards[{index}] must bind an identity_baseline_image_id")
        approved = card.get("approved_image_ids") or []
        if not approved:
            errors.append(f"template asset_identity_cards[{index}] must list approved_image_ids")
        if card.get("identity_baseline_image_id") and card.get("identity_baseline_image_id") not in approved:
            errors.append(f"template asset_identity_cards[{index}] baseline image must be approved")
        for image_id in approved:
            if str(image_id) not in generated_image_ids:
                errors.append(f"template asset_identity_cards[{index}] approved image is not generated: {image_id}")
        if card.get("human_review_status") not in {"approved", "needs_revision", "rejected"}:
            errors.append(f"template asset_identity_cards[{index}].human_review_status must be approved, needs_revision, or rejected")

    reference_chain = template.get("reference_asset_chain") or []
    if not reference_chain:
        errors.append("template reference_asset_chain must include at least one shot-to-asset reference")
    known_asset_ids = {
        str(card.get("asset_id"))
        for card in asset_cards
        if card.get("asset_id")
    }
    for index, chain in enumerate(reference_chain):
        for field in ("shot_id", "story_purpose", "referenced_assets", "continuity_note"):
            if field not in chain:
                errors.append(f"template reference_asset_chain[{index}] missing {field}")
        referenced_assets = chain.get("referenced_assets") or []
        if not referenced_assets:
            errors.append(f"template reference_asset_chain[{index}] must list referenced_assets")
        for ref_index, ref in enumerate(referenced_assets):
            for field in ("asset_id", "asset_type", "name", "identity_baseline_image_id", "approved_reference_image_ids"):
                if field not in ref:
                    errors.append(f"template reference_asset_chain[{index}].referenced_assets[{ref_index}] missing {field}")
            if ref.get("asset_id") and ref.get("asset_id") not in known_asset_ids:
                errors.append(
                    f"template reference_asset_chain[{index}].referenced_assets[{ref_index}] points to unknown asset_id"
                )
            approved_refs = ref.get("approved_reference_image_ids") or []
            if ref.get("identity_baseline_image_id") and ref.get("identity_baseline_image_id") not in approved_refs:
                errors.append(
                    f"template reference_asset_chain[{index}].referenced_assets[{ref_index}] baseline image must be an approved reference"
                )

    lineage = template.get("prompt_strategy_lineage") or {}
    if lineage.get("status") != "ready":
        errors.append("template prompt_strategy_lineage.status must show the ready target state")
    for field in ("expected_prompt_strategy_version", "package_prompt_strategy_version", "asset_prompt_count", "shot_prompt_count"):
        if field not in lineage:
            errors.append(f"template prompt_strategy_lineage must include {field}")

    director_contract = template.get("prompt_director_contract") or {}
    if director_contract.get("status") != "ready":
        errors.append("template prompt_director_contract.status must show the ready target state")
    if director_contract.get("prompt_author_department") != "bingbu":
        errors.append("template prompt_director_contract.prompt_author_department must be bingbu")
    if director_contract.get("reviewer_department") != "xingbu":
        errors.append("template prompt_director_contract.reviewer_department must be xingbu")
    negative_policy = director_contract.get("negative_prompt_policy") or {}
    if negative_policy.get("placement") != "end_only":
        errors.append("template prompt_director_contract.negative_prompt_policy.placement must be end_only")
    if negative_policy.get("prefix") != "禁止":
        errors.append("template prompt_director_contract.negative_prompt_policy.prefix must be 禁止")
    if len(negative_policy.get("forbidden_forms") or []) < 3:
        errors.append("template prompt_director_contract.negative_prompt_policy must list forbidden forms")
    required_sections = set(str(item) for item in (director_contract.get("required_sections") or []))
    expected_sections = {
        "shot_purpose",
        "reference_image_chain",
        "camera_plan",
        "performance_direction",
        "art_lighting",
        "continuity_constraints",
        "negative_prompt",
    }
    missing_sections = sorted(expected_sections - required_sections)
    if missing_sections:
        errors.append("template prompt_director_contract.required_sections missing: " + ", ".join(missing_sections))
    prompt_records = director_contract.get("shot_prompt_records") or []
    if not prompt_records:
        errors.append("template prompt_director_contract.shot_prompt_records must include at least one record")
    known_image_ids = {
        str(image.get("image_id"))
        for image in generated_images
        if image.get("image_id")
    }
    known_shot_ids = {
        str(chain.get("shot_id"))
        for chain in reference_chain
        if chain.get("shot_id")
    }
    for index, record in enumerate(prompt_records):
        for field in expected_sections | {"shot_id", "prompt_id", "template_repetition_score", "human_review_status"}:
            if field not in record:
                errors.append(f"template prompt_director_contract.shot_prompt_records[{index}] missing {field}")
        if record.get("shot_id") and record.get("shot_id") not in known_shot_ids:
            errors.append(f"template prompt_director_contract.shot_prompt_records[{index}] points to unknown shot_id")
        reference_images = [str(item) for item in (record.get("reference_image_chain") or []) if str(item).strip()]
        if not reference_images:
            errors.append(f"template prompt_director_contract.shot_prompt_records[{index}] must list reference_image_chain")
        for image_id in reference_images:
            if image_id not in known_image_ids:
                errors.append(f"template prompt_director_contract.shot_prompt_records[{index}] references unknown image_id: {image_id}")
        negative_prompt = str(record.get("negative_prompt") or "")
        if not negative_prompt.startswith("禁止"):
            errors.append(f"template prompt_director_contract.shot_prompt_records[{index}].negative_prompt must start with 禁止")
        if "不要" in negative_prompt:
            errors.append(f"template prompt_director_contract.shot_prompt_records[{index}].negative_prompt must use 禁止 instead of 不要")
        repetition_score = record.get("template_repetition_score")
        if not isinstance(repetition_score, (int, float)) or not 0 <= float(repetition_score) <= 0.3:
            errors.append(f"template prompt_director_contract.shot_prompt_records[{index}].template_repetition_score must be between 0 and 0.3")
        if record.get("human_review_status") not in {"approved", "needs_revision", "rejected"}:
            errors.append(f"template prompt_director_contract.shot_prompt_records[{index}].human_review_status must be approved, needs_revision, or rejected")

    acceptance = template.get("operator_acceptance_checklist") or {}
    for field in (
        "reviewer_role",
        "reviewed_at",
        "story_locked",
        "asset_split_approved",
        "image_quality_approved",
        "prompt_package_approved",
        "word_canvas_approved",
        "downstream_handoff_approved",
        "unresolved_questions",
        "rejected_items",
        "acceptance_note",
    ):
        if field not in acceptance:
            errors.append(f"template operator_acceptance_checklist must include {field}")
    for field in (
        "story_locked",
        "asset_split_approved",
        "image_quality_approved",
        "prompt_package_approved",
        "word_canvas_approved",
        "downstream_handoff_approved",
    ):
        if acceptance.get(field) is not True:
            errors.append(f"template operator_acceptance_checklist.{field} must show the ready target state")
    if not isinstance(acceptance.get("unresolved_questions"), list):
        errors.append("template operator_acceptance_checklist.unresolved_questions must be a list")
    if not isinstance(acceptance.get("rejected_items"), list):
        errors.append("template operator_acceptance_checklist.rejected_items must be a list")
    if not str(acceptance.get("acceptance_note") or "").strip():
        errors.append("template operator_acceptance_checklist.acceptance_note must explain the human decision")

    recovery = template.get("recovery_protocol") or {}
    if recovery.get("status") != "ready":
        errors.append("template recovery_protocol.status must show the ready target state")
    if recovery.get("default_recovery_action") != "regenerate_images":
        errors.append("template recovery_protocol.default_recovery_action must be regenerate_images")
    if recovery.get("retry_endpoint") != "/api/workspaces/{workspace_id}/comic/v2/quality/recover":
        errors.append("template recovery_protocol.retry_endpoint must expose the quality recovery endpoint")
    if "重新开盲盒" not in str(recovery.get("scope_policy") or ""):
        errors.append("template recovery_protocol.scope_policy must preserve the no-new-blind-box recovery rule")
    stage_routes = recovery.get("stage_routes") or []
    expected_failure_types = {
        "image_quality_failed": "image_generation",
        "asset_split_failed": "asset_review",
        "prompt_package_failed": "prompt_review",
        "word_canvas_missing_or_stale": "delivery_build",
    }
    seen_failure_types: set[str] = set()
    for index, route in enumerate(stage_routes):
        failure_type = str(route.get("failure_type") or "")
        seen_failure_types.add(failure_type)
        expected_stage = expected_failure_types.get(failure_type)
        if not expected_stage:
            errors.append(f"template recovery_protocol.stage_routes[{index}] has unknown failure_type")
        elif route.get("return_to_stage") != expected_stage:
            errors.append(
                f"template recovery_protocol.stage_routes[{index}] return_to_stage must be {expected_stage}"
            )
        for field in ("preserve", "clear", "reviewer_department", "operator_next_step"):
            if not route.get(field):
                errors.append(f"template recovery_protocol.stage_routes[{index}] must include {field}")
        if not isinstance(route.get("preserve"), list):
            errors.append(f"template recovery_protocol.stage_routes[{index}].preserve must be a list")
        if not isinstance(route.get("clear"), list):
            errors.append(f"template recovery_protocol.stage_routes[{index}].clear must be a list")
        if failure_type == "image_quality_failed":
            if route.get("target_image_ids_source") != "image_quality_summary.failed_image_ids":
                errors.append("template image-quality recovery must scope retries to image_quality_summary.failed_image_ids")
            if "failed_generated_images" not in (route.get("clear") or []):
                errors.append("template image-quality recovery must clear failed_generated_images")
            if "story" not in (route.get("preserve") or []):
                errors.append("template image-quality recovery must preserve story")
    missing_routes = sorted(set(expected_failure_types) - seen_failure_types)
    if missing_routes:
        errors.append("template recovery_protocol missing routes: " + ", ".join(missing_routes))
    if not str(recovery.get("acceptance") or "").strip():
        errors.append("template recovery_protocol.acceptance must explain post-recovery verification")

    delivery = template.get("delivery_files") or {}
    for field in ("word_canvas_path", "handoff_manifest_path", "trace_path", "production_acceptance_path"):
        if not delivery.get(field):
            errors.append(f"template delivery_files must include {field}")

    decision = template.get("downstream_handoff_decision") or {}
    if decision.get("status") != "ready_for_downstream":
        errors.append("template downstream_handoff_decision.status must show the ready target state")
    if decision.get("handoff_allowed") is not True:
        errors.append("template downstream_handoff_decision.handoff_allowed must show the ready target state")

    return {
        "status": "passed" if not errors else "failed",
        "path": _display_path(path),
        "schema": template.get("schema"),
        "strict_real_values": strict_real_values,
        "image_record_count": len(generated_images),
        "visual_review_count": len(reviews),
        "asset_identity_card_count": len(asset_cards),
        "reference_asset_chain_count": len(reference_chain),
        "director_prompt_record_count": len((template.get("prompt_director_contract") or {}).get("shot_prompt_records") or []),
        "director_contract_ready": (template.get("prompt_director_contract") or {}).get("status") == "ready",
        "recovery_protocol_ready": (template.get("recovery_protocol") or {}).get("status") == "ready",
        "recovery_route_count": len((template.get("recovery_protocol") or {}).get("stage_routes") or []),
        "operator_acceptance_ready": bool(acceptance) and not any(
            acceptance.get(field) is not True
            for field in (
                "story_locked",
                "asset_split_approved",
                "image_quality_approved",
                "prompt_package_approved",
                "word_canvas_approved",
                "downstream_handoff_approved",
            )
        ),
        "forbidden_marker_count": len(must_not_include),
        "errors": errors,
    }


def _is_auditable_user_manifest(path: Path) -> bool:
    """Return True when a workspace manifest is complete enough for real-run intake."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if not isinstance(payload.get("images"), list) or not payload["images"]:
        return False
    if not isinstance(payload.get("assets"), list) or not payload["assets"]:
        return False
    if not isinstance(payload.get("shots"), list) or not payload["shots"]:
        return False
    if not isinstance(payload.get("word_canvas"), dict):
        return False
    return True


def find_latest_user_handoff_manifest(output_root: Path = DEFAULT_USER_OUTPUT_ROOT) -> Path | None:
    """Find the newest auditable workspace handoff manifest without reading verifier output."""
    root = Path(output_root)
    if not root.exists():
        return None
    candidates = [
        path
        for path in root.rglob("*handoff_manifest.json")
        if path.is_file()
    ]
    auditable_candidates = [path for path in candidates if _is_auditable_user_manifest(path)]
    if not auditable_candidates:
        return None
    return max(auditable_candidates, key=lambda path: (path.stat().st_mtime, str(path)))


def _read_doc() -> tuple[str, str | None]:
    if not DOC_PATH.exists():
        return "", "missing"
    try:
        return DOC_PATH.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as exc:
        return "", f"utf8_decode_error:{exc}"


def verify_real_run_evidence_intake(manifest_path: Path | None = None) -> dict[str, Any]:
    text, read_error = _read_doc()
    template_contract = _verify_template_contract()
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
    if template_contract.get("status") != "passed":
        errors.extend(template_contract.get("errors") or ["real-run evidence intake template contract failed"])

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
        "prompt_director_contract": all(marker in text for marker in ("prompt_director_contract", "shot_purpose", "reference_image_chain", "camera_plan", "performance_direction", "continuity_constraints")),
        "word_canvas": all(marker in text for marker in ("故事合同", "资产身份证", "图片联系表", "镜头卡", "提示词包")),
        "operator_acceptance": all(marker in text for marker in ("人工验收签字", "故事锁定", "资产拆解已审核", "交给下游")),
        "recovery_protocol": all(marker in text for marker in ("recovery_protocol", "return_to_stage", "preserve", "clear", "operator_next_step")),
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
        "template_contract": template_contract,
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


def verify_real_run_evidence_file(evidence_path: Path) -> dict[str, Any]:
    text, read_error = _read_doc()
    evidence_contract = _verify_template_contract(evidence_path, strict_real_values=True)
    errors: list[str] = []

    if read_error:
        errors.append(f"real-run evidence intake doc read error: {read_error}")
    if evidence_contract.get("status") != "passed":
        errors.extend(evidence_contract.get("errors") or ["real-run evidence file contract failed"])

    image_count = int(evidence_contract.get("image_record_count") or 0)
    review_count = int(evidence_contract.get("visual_review_count") or 0)
    asset_count = int(evidence_contract.get("asset_identity_card_count") or 0)
    ready = not errors
    return {
        "status": "passed" if ready else "failed",
        "mode": "comic_real_run_evidence_intake",
        "audit_subject": "evidence_file",
        "audited_manifest": "",
        "audited_evidence_file": _display_path(evidence_path),
        "summary": (
            "Standalone real-run evidence file is complete enough to merge into the final handoff manifest."
            if ready
            else "Standalone real-run evidence file has gaps before it can be merged into the final handoff manifest."
        ),
        "document": "docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md",
        "line_count": len(text.splitlines()) if text else 0,
        "missing_marker_count": 0,
        "human_flow_step_count": 0,
        "recovery_action_count": 0,
        "template_contract": evidence_contract,
        "section_status": {
            "evidence_file_schema": evidence_contract.get("schema") == "comic_real_run_evidence_intake_v1",
            "real_values": bool(evidence_contract.get("strict_real_values")),
            "images_and_reviews": image_count > 0 and image_count == review_count,
            "asset_identity_cards": asset_count >= 3,
            "operator_acceptance": bool(evidence_contract.get("operator_acceptance_ready")),
            "recovery_protocol": bool(evidence_contract.get("recovery_protocol_ready")),
        },
        "benchmark_claim": "not_audited",
        "benchmark_real_quality_verified": False,
        "claim_level": "evidence_file_ready" if ready else "evidence_file_incomplete",
        "can_claim_real_quality": False,
        "downstream_status": "not_merged_into_handoff",
        "handoff_allowed": False,
        "real_quality_promotion_ready": False,
        "visual_evidence_level": "evidence_file_only",
        "image_quality_summary": {},
        "prompt_strategy_lineage": {},
        "real_model_evidence_requirements": {},
        "structural_downstream_handoff_ready": False,
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
        f"- Audited evidence file: `{payload.get('audited_evidence_file') or '-'}`",
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
    template = payload.get("template_contract") or {}
    if template:
        lines.extend([
            "",
            "## Evidence Template",
            "",
            f"- Status: `{template.get('status')}`",
            f"- Path: `{template.get('path')}`",
        f"- Schema: `{template.get('schema')}`",
        f"- Image records: `{template.get('image_record_count')}`",
        f"- Visual reviews: `{template.get('visual_review_count')}`",
        f"- Asset identity cards: `{template.get('asset_identity_card_count')}`",
        f"- Reference asset chains: `{template.get('reference_asset_chain_count')}`",
        f"- Director prompt records: `{template.get('director_prompt_record_count')}`",
        f"- Director contract ready: `{template.get('director_contract_ready')}`",
        f"- Recovery protocol ready: `{template.get('recovery_protocol_ready')}`",
        f"- Recovery routes: `{template.get('recovery_route_count')}`",
        f"- Operator acceptance ready: `{template.get('operator_acceptance_ready')}`",
        f"- Forbidden markers: `{template.get('forbidden_marker_count')}`",
    ])
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
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--manifest", type=Path, help="Existing comic V2 handoff manifest to audit.")
    source.add_argument(
        "--evidence-file",
        type=Path,
        help="Standalone real-run evidence JSON to validate before merging it into a handoff manifest.",
    )
    source.add_argument(
        "--latest",
        action="store_true",
        help="Audit the newest *_handoff_manifest.json under output/workspaces.",
    )
    parser.add_argument(
        "--latest-output-root",
        type=Path,
        default=DEFAULT_USER_OUTPUT_ROOT,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()
    if args.evidence_file:
        payload = verify_real_run_evidence_file(args.evidence_file)
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(format_markdown(payload))
        return 0 if payload["status"] == "passed" else 1
    manifest_path = args.manifest
    if args.latest:
        manifest_path = find_latest_user_handoff_manifest(args.latest_output_root)
        if manifest_path is None:
            payload = {
                "status": "failed",
                "mode": "comic_real_run_evidence_intake",
                "audit_subject": "latest_user_manifest",
                "audited_manifest": "",
                "summary": "No auditable user handoff manifest was found under output/workspaces.",
                "document": "docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md",
                "line_count": 0,
                "missing_marker_count": 0,
                "human_flow_step_count": 0,
                "recovery_action_count": 0,
                "section_status": {},
                "benchmark_claim": "not_audited",
                "benchmark_real_quality_verified": False,
                "claim_level": "not_audited",
                "can_claim_real_quality": False,
                "downstream_status": "not_audited",
                "handoff_allowed": False,
                "real_quality_promotion_ready": False,
                "visual_evidence_level": "not_audited",
                "structural_downstream_handoff_ready": False,
                "errors": [
                    "没有找到完整可审计的真实工作区制片包。请先在 AI 漫剧制片办公室生成包含图片、资产、镜头和 Word 画布的交付包，或使用 --manifest 指向具体的 *_handoff_manifest.json。"
                ],
            }
            if args.format == "json":
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(format_markdown(payload))
            return 1
    payload = verify_real_run_evidence_intake(manifest_path=manifest_path)
    if args.latest:
        payload["audit_subject"] = "latest_user_manifest"
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
