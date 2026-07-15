"""Cross-artifact quality benchmark for AI comic production handoffs."""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any, Callable

from .prompt_quality import audit_prompt_package
from .visual_review import REVIEW_DIMENSIONS


BENCHMARK_VERSION = 1
DIMENSION_WEIGHT = 20
READY_SCORE = 85

REQUIRED_IMAGE_KINDS = {
    "character": {"three_view", "expression_sheet"},
    "prop": {"turnaround"},
    "scene": {"wide", "top_down"},
}

DIRECTOR_FIELDS = {
    "style_id",
    "style_version",
    "first_frame_image_id",
    "reference_asset_ids",
    "action_chain",
    "performance_intent",
    "framing",
    "camera_movement",
    "lighting",
    "dialogue",
    "sound",
}


def audit_handoff_manifest(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Audit whether a handoff is grounded, specific, traceable, and honestly reviewed."""
    manifest = payload if isinstance(payload, dict) else {}
    story = manifest.get("story") or {}
    style = manifest.get("style") or {}
    assets = list(manifest.get("assets") or [])
    images = list(manifest.get("images") or [])
    shots = list(manifest.get("shots") or [])
    lineage = list(manifest.get("production_lineage") or [])
    visual_evidence = _visual_evidence_level(images)

    dimensions = [
        _story_grounding(story, assets, shots),
        _asset_identity(style, assets, images),
        _prompt_specificity(assets, images, shots),
        _director_execution(style, story, assets, images, shots),
        _visual_evidence(style, images, lineage, visual_evidence),
    ]
    score = round(sum(item["score"] * item["weight"] for item in dimensions) / 100)
    issues = []
    for dimension in dimensions:
        for check in dimension["checks"]:
            if check["status"] == "passed":
                continue
            recovery = _recovery_for_issue(check["code"])
            issues.append({
                "code": check["code"],
                "dimension": dimension["id"],
                "severity": check["severity"],
                "message": check["message"],
                "evidence": check["evidence"],
                "department": recovery["department"],
                "recovery_action": recovery["action"],
                "recovery_focus": recovery["focus"],
            })
    blockers = [item for item in issues if item["severity"] == "blocker"]
    package_quality_ready = score >= READY_SCORE and not blockers
    production_quality_verified = (
        package_quality_ready
        and visual_evidence == "model_reviewed"
        and not any(item["dimension"] == "visual_evidence" for item in issues)
    )
    if not package_quality_ready:
        claim = "needs_review"
    elif production_quality_verified:
        claim = "production_quality_verified"
    else:
        claim = "demo_structure_verified"
    recommended_recovery = _recommended_recovery(issues)

    limitations = []
    if visual_evidence == "fixture_only":
        limitations.append(
            "当前图片来自无 Key 固定样例，只证明流程、引用和交付结构；不证明真实模型的画风或人物一致性。"
        )
    elif visual_evidence == "mixed_or_unknown":
        limitations.append("图片来源或视觉质检证据不完整，不能宣称真实生产质量已验证。")

    return {
        "benchmark": "comic_production_package_quality",
        "benchmark_version": BENCHMARK_VERSION,
        "status": claim,
        "package_quality_score": score,
        "package_quality_ready": package_quality_ready,
        "production_quality_verified": production_quality_verified,
        "visual_evidence_level": visual_evidence,
        "summary": _summary(claim, score),
        "dimensions": dimensions,
        "issue_count": len(issues),
        "blocker_count": len(blockers),
        "issues": issues,
        "limitations": limitations,
        "recommended_recovery": recommended_recovery,
        "next_action": _next_action(claim, recommended_recovery),
    }


def _story_grounding(
    story: dict[str, Any],
    assets: list[dict[str, Any]],
    shots: list[dict[str, Any]],
) -> dict[str, Any]:
    source = str(story.get("source_story") or "")
    expected_hash = str(story.get("source_hash") or "")
    checks = [
        _check(
            "story.source_present",
            bool(source.strip()),
            "交接清单保留了用户确认的完整故事。",
            "交接清单缺少完整故事，无法独立验证资产和镜头是否跑偏。",
            f"chars={len(source)}",
        ),
        _check(
            "story.source_hash",
            bool(source) and hashlib.sha256(source.encode("utf-8")).hexdigest() == expected_hash,
            "完整故事与确认版本哈希一致。",
            "故事原文与确认版本哈希不一致，交付链可能混入了另一版故事。",
            expected_hash[:12] if expected_hash else "missing",
        ),
        _collection_check(
            "story.asset_evidence",
            assets,
            lambda item: bool(item.get("evidence_quote")) and str(item["evidence_quote"]) in source,
            "所有资产都能回指确认故事中的原文证据。",
            "存在资产无法回指确认故事原文。",
        ),
        _collection_check(
            "story.shot_evidence",
            shots,
            lambda item: bool(item.get("evidence_quote")) and str(item["evidence_quote"]) in source,
            "所有镜头都能回指确认故事中的原文证据。",
            "存在镜头无法回指确认故事原文。",
        ),
    ]
    return _dimension("story_grounding", "故事贴合度", checks)


def _asset_identity(
    style: dict[str, Any],
    assets: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    image_ids = {str(item.get("image_id") or "") for item in images}
    image_keys = {
        (str(item.get("asset_id") or ""), str(item.get("image_kind") or ""))
        for item in images
    }
    style_id = str(style.get("style_id") or "")
    style_version = _as_int(style.get("style_version"))
    checks = [
        _collection_check(
            "asset.identity_card",
            assets,
            lambda item: bool(item.get("asset_id"))
            and bool(item.get("name"))
            and bool(item.get("story_purpose"))
            and bool(item.get("visual_locks"))
            and bool(item.get("planned_images")),
            "每项资产都有名称、用途、视觉锁定和计划图组。",
            "存在不完整的资产身份证。",
        ),
        _collection_check(
            "asset.required_views",
            assets,
            lambda item: REQUIRED_IMAGE_KINDS.get(str(item.get("asset_type") or ""), set()).issubset(
                set(item.get("planned_images") or [])
            ),
            "人物、道具和场景都包含最低生产视图。",
            "存在资产缺少三视图、表情表、转面、广角或俯视图。",
        ),
        _collection_check(
            "asset.image_coverage",
            assets,
            lambda item: all(
                (str(item.get("asset_id") or ""), str(kind)) in image_keys
                for kind in (item.get("planned_images") or [])
            ),
            "所有计划图都对应一条图片记录。",
            "部分计划图没有对应图片记录。",
        ),
        _collection_check(
            "asset.identity_baseline",
            assets,
            lambda item: bool(item.get("identity_baseline_image_id"))
            and str(item.get("identity_baseline_image_id")) in image_ids,
            "每项资产都有可引用的身份基准图。",
            "存在资产缺少身份基准图。",
        ),
        _collection_check(
            "asset.version_binding",
            images,
            lambda item: str(item.get("style_id") or "") == style_id
            and _as_int(item.get("style_version")) == style_version
            and _as_int(item.get("story_version")) > 0
            and _as_int(item.get("manifest_version")) > 0,
            "所有图片都绑定当前故事、视觉母版和资产清单版本。",
            "存在图片版本绑定缺失或与当前视觉母版不一致。",
        ),
    ]
    return _dimension("asset_identity", "资产身份证与一致性", checks)


def _prompt_specificity(
    assets: list[dict[str, Any]],
    images: list[dict[str, Any]],
    shots: list[dict[str, Any]],
) -> dict[str, Any]:
    assets_by_id = {str(item.get("asset_id") or ""): item for item in assets}
    prompt_audit = audit_prompt_package({
        "prompts": [
            {
                "object_id": item.get("asset_id", ""),
                "image_kind": item.get("image_kind", ""),
                "production_role": item.get("production_role", ""),
                "clean_background_required": item.get("clean_background_required"),
                "generator_prompt": item.get("generator_prompt", ""),
                "negative_prompt": item.get("negative_prompt") or [],
            }
            for item in images
        ],
        "shots": [
            {
                "shot_id": item.get("shot_id", ""),
                "generator_prompt": item.get("video_prompt_block", ""),
                "negative_prompt": _split_negative(item.get("negative_prompt_block", "")),
            }
            for item in shots
        ],
    })
    duplicate_pairs = _duplicate_asset_prompt_pairs(images, assets_by_id)
    checks = [
        _check(
            "prompt.executable_structure",
            prompt_audit.get("status") == "ready",
            "资产和镜头提示词满足可执行结构要求。",
            "提示词存在白底、空场景、导演字段或负面提示词问题。",
            f"issues={prompt_audit.get('issue_count', 0)}",
        ),
        _collection_check(
            "prompt.asset_name_grounding",
            images,
            lambda item: bool(str(assets_by_id.get(str(item.get("asset_id") or ""), {}).get("name") or ""))
            and str(assets_by_id.get(str(item.get("asset_id") or ""), {}).get("name") or "")
            in str(item.get("generator_prompt") or ""),
            "每条基础图提示词都写明当前资产名称。",
            "存在提示词没有写明当前资产名称。",
        ),
        _collection_check(
            "prompt.visual_lock_grounding",
            images,
            lambda item: any(
                str(lock) in str(item.get("generator_prompt") or "")
                for lock in assets_by_id.get(str(item.get("asset_id") or ""), {}).get("visual_locks", [])
            ),
            "每条基础图提示词都落实了当前资产的专属视觉锁定。",
            "存在提示词只写通用画风，没有落实资产视觉锁定。",
        ),
        _check(
            "prompt.cross_asset_uniqueness",
            not duplicate_pairs,
            "不同资产的提示词具有可辨认的专属内容。",
            "不同资产的提示词高度雷同，疑似复制模板后只替换名称。",
            ", ".join(duplicate_pairs[:4]) if duplicate_pairs else "no near-duplicates",
        ),
    ]
    return _dimension("prompt_specificity", "提示词专属性", checks)


def _director_execution(
    style: dict[str, Any],
    story: dict[str, Any],
    assets: list[dict[str, Any]],
    images: list[dict[str, Any]],
    shots: list[dict[str, Any]],
) -> dict[str, Any]:
    asset_ids = {str(item.get("asset_id") or "") for item in assets}
    image_ids = {str(item.get("image_id") or "") for item in images}
    style_id = str(style.get("style_id") or "")
    style_version = _as_int(style.get("style_version"))
    source = str(story.get("source_story") or "")

    def valid_director(shot: dict[str, Any]) -> bool:
        director = shot.get("director_execution") or {}
        return (
            not [field for field in DIRECTOR_FIELDS if director.get(field) in (None, "", [])]
            and str(director.get("style_id") or "") == style_id
            and _as_int(director.get("style_version")) == style_version
            and set(director.get("reference_asset_ids") or []).issubset(asset_ids)
            and str(director.get("first_frame_image_id") or "") in image_ids
            and len(director.get("action_chain") or []) >= 2
        )

    fingerprints = {
        "|".join(
            str((shot.get("director_execution") or {}).get(field) or "").strip()
            for field in ("performance_intent", "framing", "camera_movement", "lighting")
        )
        for shot in shots
    }
    varied = len(shots) < 2 or len(fingerprints) > 1
    checks = [
        _collection_check(
            "director.contract_complete",
            shots,
            valid_director,
            "每个镜头都有完整且版本一致的导演执行合同。",
            "存在镜头缺少动作、表演、摄影、灯光、声音或有效首帧引用。",
        ),
        _collection_check(
            "director.story_grounding",
            shots,
            lambda item: bool(item.get("evidence_quote")) and str(item["evidence_quote"]) in source,
            "每个镜头都有确认故事中的逐字依据。",
            "存在镜头脱离确认故事原文。",
        ),
        _collection_check(
            "director.acceptance_and_retry",
            shots,
            lambda item: len(item.get("acceptance_criteria") or []) >= 3
            and bool(item.get("retry_strategy"))
            and bool(item.get("platform_note")),
            "每个镜头都有验收标准、重试策略和平台说明。",
            "存在镜头缺少验收、重试或下游执行说明。",
        ),
        _check(
            "director.scene_specificity",
            varied,
            "镜头的表演、景别、摄影或灯光会随剧情节点变化。",
            "多个镜头使用完全相同的导演参数，建议由兵部重新按场次设计。",
            f"unique_fingerprints={len(fingerprints)}/{len(shots)}",
            severity="warning",
        ),
    ]
    return _dimension("director_execution", "导演执行力", checks)


def _visual_evidence(
    style: dict[str, Any],
    images: list[dict[str, Any]],
    lineage: list[dict[str, Any]],
    evidence_level: str,
) -> dict[str, Any]:
    required_stages = {
        "story_contract",
        "visual_bible",
        "asset_manifest",
        "prompt_package",
        "image_production",
        "visual_review",
        "delivery",
    }
    checks = [
        _collection_check(
            "visual.approved_images",
            images,
            lambda item: str(item.get("status") or "") == "approved",
            "所有交付图片都已通过当前流程审批。",
            "存在尚未批准的图片。",
        ),
        _collection_check(
            "visual.review_handoff",
            images,
            lambda item: bool((item.get("review") or {}).get("handoff_ready")),
            "每张图片都保留了可交接的视觉质检结论。",
            "存在图片缺少真实视觉质检结论。",
        ),
        _collection_check(
            "visual.reference_chain",
            [item for item in images if not item.get("is_identity_baseline")],
            lambda item: bool(item.get("reference_image_ids")),
            "非基准图都引用了已批准身份图。",
            "存在后续图片没有引用身份基准图。",
            allow_empty=True,
        ),
        _check(
            "visual.lineage",
            required_stages.issubset({str(item.get("stage") or "") for item in lineage}),
            "生产谱系覆盖故事、资产、提示词、生图、质检和交付。",
            "生产谱系缺少关键阶段。",
            f"stages={len(lineage)}",
        ),
    ]
    if evidence_level == "model_reviewed":
        checks.append(_collection_check(
            "visual.review_dimensions",
            images,
            lambda item: _review_scores_ready(item.get("review") or {}),
            "真实模型质检覆盖身份、风格、时代、空间、纯净度、结构和用途七个维度。",
            "真实模型质检缺少七维评分，不能宣称生产质量已验证。",
        ))
    else:
        checks.append(_check(
            "visual.fixture_disclosure",
            evidence_level == "fixture_only",
            "无 Key 固定样例已明确标注，不冒充真实模型画质验证。",
            "图片来源混合或未知，视觉证据边界不清楚。",
            evidence_level,
            severity="warning",
        ))
    return _dimension("visual_evidence", "视觉质检与追溯", checks)


def _visual_evidence_level(images: list[dict[str, Any]]) -> str:
    providers = {str(item.get("provider") or "").strip().lower() for item in images}
    if providers == {"fixture"}:
        return "fixture_only"
    if images and "fixture" not in providers and "" not in providers:
        return "model_reviewed"
    return "mixed_or_unknown"


def _review_scores_ready(review: dict[str, Any]) -> bool:
    scores = review.get("scores") or {}
    if not isinstance(scores, dict) or not set(scores).issuperset(REVIEW_DIMENSIONS):
        return False
    try:
        return all(int(float(scores[dimension])) >= 80 for dimension in REVIEW_DIMENSIONS)
    except (TypeError, ValueError):
        return False


def _duplicate_asset_prompt_pairs(
    images: list[dict[str, Any]],
    assets_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    normalized = []
    for image in images:
        asset_id = str(image.get("asset_id") or "")
        asset = assets_by_id.get(asset_id, {})
        body = _normalize_prompt(
            str(image.get("generator_prompt") or ""),
            asset_id,
            str(asset.get("name") or ""),
        )
        normalized.append((asset_id, str(asset.get("asset_type") or ""), body))
    pairs = []
    for index, left in enumerate(normalized):
        for right in normalized[index + 1:]:
            if not left[0] or left[0] == right[0] or left[1] != right[1]:
                continue
            if min(len(left[2]), len(right[2])) < 60:
                continue
            ratio = SequenceMatcher(None, left[2], right[2]).ratio()
            if ratio >= 0.92:
                pairs.append(f"{left[0]}~{right[0]}:{ratio:.2f}")
    return pairs


def _normalize_prompt(text: str, asset_id: str, asset_name: str) -> str:
    value = str(text or "")
    for token in (asset_id, asset_name):
        if token:
            value = value.replace(token, "")
    sentences = re.split(r"[。；\n]+", value)
    filtered = [
        sentence
        for sentence in sentences
        if sentence.strip()
        and not any(marker in sentence for marker in ("风格身份", "画面比例", "资产ID", "资产名称"))
    ]
    return re.sub(r"[\s，,:：、]+", "", "。".join(filtered))


def _split_negative(text: Any) -> list[str]:
    return [item.strip() for item in str(text or "").split("；") if item.strip()]


def _collection_check(
    code: str,
    items: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    success: str,
    failure: str,
    *,
    severity: str = "blocker",
    allow_empty: bool = False,
) -> dict[str, Any]:
    failed = [
        str(item.get("asset_id") or item.get("image_id") or item.get("shot_id") or "<unknown>")
        for item in items
        if not predicate(item)
    ]
    return _check(
        code,
        (bool(items) or allow_empty) and not failed,
        success,
        failure,
        f"passed={len(items) - len(failed)}/{len(items)}"
        + (f"; failed={','.join(failed[:6])}" if failed else ""),
        severity=severity,
    )


def _check(
    code: str,
    passed: bool,
    success: str,
    failure: str,
    evidence: str,
    *,
    severity: str = "blocker",
) -> dict[str, Any]:
    return {
        "code": code,
        "status": "passed" if passed else ("warning" if severity == "warning" else "failed"),
        "severity": severity,
        "message": success if passed else failure,
        "evidence": evidence,
    }


def _dimension(dimension_id: str, label: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    values = {"passed": 1.0, "warning": 0.6, "failed": 0.0}
    score = round(100 * sum(values[item["status"]] for item in checks) / max(1, len(checks)))
    if any(item["status"] == "failed" for item in checks):
        status = "failed"
    elif any(item["status"] == "warning" for item in checks):
        status = "warning"
    else:
        status = "passed"
    return {
        "id": dimension_id,
        "label": label,
        "weight": DIMENSION_WEIGHT,
        "status": status,
        "score": score,
        "checks": checks,
    }


def _summary(claim: str, score: int) -> str:
    if claim == "production_quality_verified":
        return f"制片包质量基准通过（{score}/100），并具有真实模型七维视觉质检证据。"
    if claim == "demo_structure_verified":
        return f"制片包结构质量基准通过（{score}/100）；当前为无 Key 样例，不代表真实模型画质。"
    return f"制片包质量需要复核（{score}/100），请先处理阻塞项再交给下游生产。"


def _next_action(claim: str, recovery: dict[str, Any]) -> str:
    if claim == "production_quality_verified":
        return "可以按镜头导演执行合同进入下游图生视频或剪辑流程。"
    if claim == "demo_structure_verified":
        return "公开展示时保留无 Key 样例声明；真实创作时再运行同一基准检查真实模型产物。"
    return str(recovery.get("description") or "请复核质量警告后再继续生产。")


def _recommended_recovery(issues: list[dict[str, Any]]) -> dict[str, Any]:
    issue = next((item for item in issues if item.get("severity") == "blocker"), None)
    issue = issue or (issues[0] if issues else None)
    if not issue:
        return {}
    recovery = _recovery_for_issue(str(issue.get("code") or ""))
    return {
        **recovery,
        "reason_code": str(issue.get("code") or ""),
        "description": str(issue.get("message") or recovery.get("description") or ""),
        "operator_steps": _operator_steps_for_recovery(str(recovery.get("action") or "")),
        "expected_stage": _expected_stage_for_recovery(str(recovery.get("action") or "")),
        "preserves": _preserved_artifacts_for_recovery(str(recovery.get("action") or "")),
        "clears": _cleared_artifacts_for_recovery(str(recovery.get("action") or "")),
    }


def _operator_steps_for_recovery(action: str) -> list[str]:
    if action == "restart_story_review":
        return [
            "返回故事确认区，重新确认完整故事原文和故事版本。",
            "重新生成故事合同、视觉母版和资产拆解，避免覆盖旧交付历史。",
        ]
    if action == "revise_assets":
        return [
            "打开资产审核区，按问题说明补充、删除或重命名人物、道具、场景。",
            "确认新版资产拆解包后，再重新生成提示词、图片和 Word 画布。",
        ]
    if action == "regenerate_prompts":
        return [
            "保留已批准资产，回到提示词和镜头规划阶段。",
            "重新生成资产提示词、镜头视频提示词和导演执行卡，再进入生图。",
        ]
    if action == "regenerate_images":
        return [
            "保留故事、资产和提示词包，回到图片生成阶段。",
            "重新生成未达标图片并执行视觉质检，再重组 Word 画布。",
        ]
    if action == "rebuild_delivery":
        return [
            "保留图片生产记录，回到交付组装阶段。",
            "重新生成 Word 制片画布、handoff manifest 和生产谱系审计。",
        ]
    return [
        "打开工作台复核质量警告。",
        "按责任部门处理阻塞项后重新运行交付审计。",
    ]


def _expected_stage_for_recovery(action: str) -> str:
    return {
        "restart_story_review": "story_confirmed",
        "revise_assets": "asset_review",
        "regenerate_prompts": "prompt_planning",
        "regenerate_images": "image_generation",
        "rebuild_delivery": "document_generation",
    }.get(action, "manual_review")


def _preserved_artifacts_for_recovery(action: str) -> list[str]:
    return {
        "restart_story_review": ["old_history", "old_word_canvas", "old_handoff_manifest"],
        "revise_assets": ["story_contract", "visual_bible", "old_history"],
        "regenerate_prompts": ["story_contract", "visual_bible", "asset_manifest"],
        "regenerate_images": ["story_contract", "visual_bible", "asset_manifest", "prompt_package"],
        "rebuild_delivery": ["story_contract", "visual_bible", "asset_manifest", "prompt_package", "image_production"],
    }.get(action, ["available_history"])


def _cleared_artifacts_for_recovery(action: str) -> list[str]:
    return {
        "restart_story_review": ["current_production_chain"],
        "revise_assets": ["prompt_package", "image_production", "delivery"],
        "regenerate_prompts": ["prompt_package", "image_production", "delivery"],
        "regenerate_images": ["image_production", "delivery"],
        "rebuild_delivery": ["delivery"],
    }.get(action, ["blocked_delivery"])


def _recovery_for_issue(code: str) -> dict[str, str]:
    if code in {"story.source_present", "story.source_hash"}:
        return {
            "department": "内阁 / 中书省 / 门下省",
            "action": "restart_story_review",
            "focus": "story",
            "label": "返回故事确认",
            "description": "故事版本或原文证据不一致，请返回故事确认并重新建立生产合同。",
        }
    if code == "story.asset_evidence" or code in {"asset.identity_card", "asset.required_views"}:
        return {
            "department": "中书省 / 门下省",
            "action": "revise_assets",
            "focus": "assets",
            "label": "退回资产拆解",
            "description": "退回资产审核，修正故事依据、资产身份证或计划图组。",
        }
    if code == "story.shot_evidence" or code.startswith("prompt.") or code.startswith("director."):
        return {
            "department": "工部 / 兵部 / 刑部",
            "action": "regenerate_prompts",
            "focus": "prompts",
            "label": "重新生成提示词和镜头卡",
            "description": "保留已批准资产，退回提示词与镜头规划并重新生成专属内容。",
        }
    if code in {"asset.image_coverage", "asset.identity_baseline", "asset.version_binding"}:
        return {
            "department": "工部 / 刑部",
            "action": "regenerate_images",
            "focus": "images",
            "label": "重新生成并质检图片",
            "description": "保留已批准资产和提示词，补齐身份基准图、计划图组和版本绑定后重新质检。",
        }
    if code == "visual.lineage":
        return {
            "department": "礼部 / 刑部",
            "action": "rebuild_delivery",
            "focus": "delivery",
            "label": "重新组装交付物",
            "description": "重新组装 Word 与引用清单，补齐生产谱系和交付审计。",
        }
    if code.startswith("visual."):
        return {
            "department": "工部 / 刑部",
            "action": "regenerate_images",
            "focus": "images",
            "label": "重新生成并质检图片",
            "description": "保留故事、资产和提示词，重新生成未通过图片并执行七维视觉质检。",
        }
    return {
        "department": "尚书省 / 刑部",
        "action": "review_package",
        "focus": "delivery",
        "label": "复核制片包",
        "description": "返回工作台复核制片包质量问题。",
    }


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
