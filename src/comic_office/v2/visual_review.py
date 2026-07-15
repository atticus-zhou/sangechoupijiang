"""Reference-aware visual review contracts for comic production V2."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


REVIEW_DIMENSIONS = (
    "identity_consistency",
    "style_consistency",
    "era_media",
    "spatial_structure",
    "asset_purity",
    "anatomy",
    "purpose_fit",
)


@dataclass(frozen=True)
class VisualReviewRequest:
    current_image: str
    reference_images: tuple[str, ...]
    previous_accepted_image: str
    visual_bible_summary: str
    acceptance_criteria: tuple[str, ...]
    image_paths: tuple[str, ...]
    image_roles: tuple[str, ...]
    instruction: str
    production_role: str = ""
    clean_background_required: bool = False


@dataclass(frozen=True)
class VisualReviewResult:
    status: str
    handoff_ready: bool
    consistency_status: str
    scores: dict[str, int]
    issues: tuple[str, ...]
    evidence: tuple[str, ...]
    revision_prompt: str
    missing_dimensions: tuple[str, ...]
    failed_dimensions: tuple[str, ...]
    reference_count: int


def build_visual_review_request(
    current_image: str,
    reference_images: list[str] | tuple[str, ...],
    *,
    previous_accepted_image: str = "",
    visual_bible_summary: str = "",
    acceptance_criteria: list[str] | tuple[str, ...] = (),
    production_role: str = "",
    clean_background_required: bool = False,
) -> VisualReviewRequest:
    """Label every image so the vision model knows what it must compare."""
    current = (current_image or "").strip()
    if not current:
        raise ValueError("current image is required")
    references = tuple(str(path).strip() for path in reference_images if str(path).strip())
    previous = (previous_accepted_image or "").strip()
    criteria = tuple(str(item).strip() for item in acceptance_criteria if str(item).strip())
    paths = (current,) + references + ((previous,) if previous else ())
    roles = ("current",) + ("approved_reference",) * len(references) + (("previous_accepted",) if previous else ())
    image_guide = ["图1：当前待检图。"]
    image_guide.extend(
        f"图{index + 2}：批准参考图，只用于比较身份、画风、道具或空间结构。"
        for index in range(len(references))
    )
    if previous:
        image_guide.append(f"图{len(paths)}：上一张合格图，用于检查相邻镜头连续性。")
    production_role = (production_role or "").strip()
    background_rule = (
        "必须是纯白或近白色干净背景，不能有剧情场景"
        if clean_background_required
        else "不强制白底；如果是场景图，应保留空间结构和环境层次"
    )
    instruction = "\n".join([
        "你是AI漫剧办公室的视觉总监和一致性质检员。",
        *image_guide,
        f"production_role: {production_role or 'unlabeled'}",
        f"clean_background_required: {bool(clean_background_required)}；{background_rule}",
        f"视觉母版：{visual_bible_summary or '未提供'}",
        f"验收标准：{'；'.join(criteria) if criteria else '按七个质量维度执行'}",
        "必须分别给出 identity_consistency、style_consistency、era_media、spatial_structure、asset_purity、anatomy、purpose_fit 的0-100分。",
        "没有批准参考图时，禁止声称身份一致性或画风一致性已经通过。",
        "只返回JSON，并为问题提供可执行的 revision_prompt。",
    ])
    return VisualReviewRequest(
        current_image=current,
        reference_images=references,
        previous_accepted_image=previous,
        visual_bible_summary=(visual_bible_summary or "").strip(),
        acceptance_criteria=criteria,
        image_paths=paths,
        image_roles=roles,
        instruction=instruction,
        production_role=production_role,
        clean_background_required=bool(clean_background_required),
    )


def normalize_visual_review(
    payload: dict[str, Any],
    request: VisualReviewRequest,
    *,
    minimum_score: int = 80,
) -> VisualReviewResult:
    """Normalize a vision response and enforce honest consistency claims."""
    raw_scores = payload.get("scores") if isinstance(payload, dict) else None
    raw_scores = raw_scores if isinstance(raw_scores, dict) else {}
    scores: dict[str, int] = {}
    missing = []
    for dimension in REVIEW_DIMENSIONS:
        score = _score(raw_scores.get(dimension))
        if score is None:
            missing.append(dimension)
        else:
            scores[dimension] = score
    failed = [dimension for dimension, score in scores.items() if score < minimum_score]
    issues = _string_tuple(payload.get("issues") if isinstance(payload, dict) else ())
    evidence = _string_tuple(payload.get("evidence") if isinstance(payload, dict) else ())
    revision_prompt = str(payload.get("revision_prompt") or "").strip() if isinstance(payload, dict) else ""
    reference_count = len(request.reference_images) + (1 if request.previous_accepted_image else 0)

    if not request.reference_images:
        consistency_status = "not_evaluated"
        issues = _append_unique(issues, "缺少批准参考图")
    elif any(dimension in failed or dimension in missing for dimension in ("identity_consistency", "style_consistency")):
        consistency_status = "fail"
    else:
        consistency_status = "pass"

    declared_status = str(payload.get("status") or "needs_review").strip().lower() if isinstance(payload, dict) else "needs_review"
    if failed or declared_status in {"fail", "failed", "不合格"}:
        status = "fail"
    elif missing or not request.reference_images or declared_status not in {"pass", "passed", "ok", "通过"}:
        status = "needs_review"
    else:
        status = "pass"
    handoff_ready = status == "pass" and consistency_status == "pass" and not missing and not failed
    return VisualReviewResult(
        status=status,
        handoff_ready=handoff_ready,
        consistency_status=consistency_status,
        scores=scores,
        issues=issues,
        evidence=evidence,
        revision_prompt=revision_prompt,
        missing_dimensions=tuple(missing),
        failed_dimensions=tuple(failed),
        reference_count=reference_count,
    )


def normalize_baseline_review(
    payload: dict[str, Any],
    request: VisualReviewRequest,
    *,
    minimum_score: int = 80,
) -> VisualReviewResult:
    """Approve the first identity sheet as a baseline without claiming cross-image consistency."""
    result = normalize_visual_review(payload, request, minimum_score=minimum_score)
    declared = str(payload.get("status") or "").strip().lower() if isinstance(payload, dict) else ""
    complete = not result.missing_dimensions and not result.failed_dimensions
    passed = declared in {"pass", "passed", "ok", "通过"} and complete
    issues = tuple(issue for issue in result.issues if issue != "缺少批准参考图")
    return replace(
        result,
        status="pass" if passed else ("fail" if result.failed_dimensions else "needs_review"),
        handoff_ready=passed,
        consistency_status="baseline_established" if passed else "baseline_failed",
        issues=issues,
        reference_count=0,
    )


def _score(value: Any) -> int | None:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return None
    if not 0 <= score <= 100:
        return None
    return score


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else values + (value,)
