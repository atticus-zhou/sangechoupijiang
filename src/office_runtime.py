"""Runtime status summaries for office workspaces.

This module turns the durable workspace, task, event, and artifact records into
a compact product-facing status view. It is intentionally read-only: the UI can
use it to explain what is happening without mutating the workflow.
"""

from __future__ import annotations

from src.offices import get_office
from src.office_recovery_registry import enriched_recovery_actions


TERMINAL_STATUSES = {"completed", "failed", "interrupted", "cancelled"}


def build_office_runtime_status(config_manager, workspace_id: str) -> dict:
    workspace = config_manager.get_workspace(workspace_id)
    if not workspace:
        return {}

    office = get_office(workspace.get("office_id", "research"))
    artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
    tasks = [
        config_manager.get_task_run(task["task_id"])
        for task in config_manager.list_workspace_task_runs(workspace_id=workspace_id)
    ]
    tasks = [task for task in tasks if task]
    active_task = _select_active_task(tasks)

    return {
        "workspace_id": workspace["workspace_id"],
        "workspace_title": workspace.get("title", ""),
        "workspace_status": workspace.get("status", ""),
        "office_id": office.id,
        "office_name": office.name,
        "current_stage": _current_stage(active_task, artifacts),
        "active_task": _task_summary(active_task),
        "artifact_progress": _artifact_progress(office.id, office.artifact_types, artifacts),
        "downloadable_artifacts": _downloadable_artifacts(artifacts),
        "delivery_acceptance": _delivery_acceptance(office.id, artifacts),
        "human_checkpoints": office.human_checkpoints,
        "recovery_actions": enriched_recovery_actions(office.id),
        "stage_lanes": _stage_lanes(office),
        "next_action": _next_action(active_task, office, artifacts),
    }


def _select_active_task(tasks: list[dict]) -> dict:
    if not tasks:
        return {}
    for task in tasks:
        if task.get("status") not in TERMINAL_STATUSES:
            return task
    return tasks[0]


def _current_stage(active_task: dict, artifacts: list[dict]) -> dict:
    if active_task:
        return {
            "id": active_task.get("current_phase") or active_task.get("status") or "unknown",
            "status": active_task.get("status") or "unknown",
            "task_id": active_task.get("task_id", ""),
            "summary": active_task.get("error") or _last_event_summary(active_task) or "任务状态已记录。",
        }
    if artifacts:
        return {
            "id": "artifacts_available",
            "status": "ready",
            "task_id": "",
            "summary": "工作空间已有产物，可继续审核、下载或补齐缺失内容。",
        }
    return {
        "id": "not_started",
        "status": "waiting",
        "task_id": "",
        "summary": "还没有任务记录，用户需要先在工作台开始一次生产或调研。",
    }


def _last_event_summary(task: dict) -> str:
    events = task.get("events") or []
    if not events:
        return ""
    return str(events[-1].get("summary") or "")


def _task_summary(task: dict) -> dict:
    if not task:
        return {}
    return {
        "task_id": task.get("task_id", ""),
        "status": task.get("status", ""),
        "current_phase": task.get("current_phase", ""),
        "error": task.get("error", ""),
        "updated_at": task.get("updated_at", ""),
        "event_count": len(task.get("events") or []),
        "last_event": (task.get("events") or [{}])[-1],
        "recovery_plan": task.get("recovery_plan", {}),
    }


def _artifact_progress(office_id: str, expected_types: list[str], artifacts: list[dict]) -> dict:
    by_type: dict[str, list[dict]] = {}
    for artifact in artifacts:
        raw_type = str(artifact.get("artifact_type") or "")
        for artifact_type in _artifact_type_aliases(office_id, raw_type):
            by_type.setdefault(artifact_type, []).append(artifact)

    present = [artifact_type for artifact_type in expected_types if artifact_type in by_type]
    missing = [artifact_type for artifact_type in expected_types if artifact_type not in by_type]
    expected = len(expected_types)
    return {
        "expected_count": expected,
        "present_count": len(present),
        "missing_count": len(missing),
        "completion_ratio": round(len(present) / expected, 4) if expected else 1.0,
        "present": present,
        "missing": missing,
        "items": [
            {
                "artifact_type": artifact_type,
                "status": "present" if artifact_type in by_type else "missing",
                "count": len(by_type.get(artifact_type, [])),
                "latest_artifact_id": by_type.get(artifact_type, [{}])[-1].get("artifact_id", ""),
                "latest_title": by_type.get(artifact_type, [{}])[-1].get("title", ""),
            }
            for artifact_type in expected_types
        ],
    }


def _downloadable_artifacts(artifacts: list[dict]) -> list[dict]:
    downloadable = []
    for artifact in artifacts:
        uri = str(artifact.get("uri") or "")
        metadata = artifact.get("metadata") or {}
        if not uri:
            uri = str(metadata.get("download_uri") or "")
        if not uri:
            continue
        downloadable.append(
            {
                "artifact_id": artifact.get("artifact_id", ""),
                "artifact_type": artifact.get("artifact_type", ""),
                "title": artifact.get("title", ""),
                "uri": uri,
                "created_by": artifact.get("created_by", ""),
                "created_at": artifact.get("created_at", ""),
            }
        )
    return sorted(downloadable, key=_download_priority)


def _artifact_type_aliases(office_id: str, artifact_type: str) -> list[str]:
    aliases = [artifact_type] if artifact_type else []
    if office_id != "comic_production":
        return aliases
    comic_v2_aliases = {
        "confirmed_script": ["script", "story_contract"],
        "comic_v2_contract": [
            "story_contract",
            "production_brief",
            "production_review",
            "script",
            "style_bible",
            "continuity_bible",
        ],
        "comic_v2_asset_manifest": [
            "asset_review_package",
            "asset_registry",
            "character_sheet",
            "prop_sheet",
            "scene_sheet",
        ],
        "comic_v2_prompt_package": ["prompt_package", "shot_prompt_table", "dispatch_plan"],
        "comic_v2_generated_image": ["generated_image", "image_quality_report"],
        "comic_v2_word_canvas": ["word_canvas", "platform_delivery_spec", "production_chain_state"],
        "comic_v2_handoff_manifest": ["quality_report", "platform_delivery_spec", "production_chain_state"],
    }
    for alias in comic_v2_aliases.get(artifact_type, []):
        if alias not in aliases:
            aliases.append(alias)
    return aliases


def _download_priority(artifact: dict) -> tuple[int, str]:
    artifact_type = str(artifact.get("artifact_type") or "")
    priority = {
        "comic_v2_word_canvas": 0,
        "word_canvas": 0,
        "comic_v2_handoff_manifest": 1,
        "prompt_package": 2,
        "comic_v2_prompt_package": 2,
        "quality_report": 3,
        "image_quality_report": 3,
        "comic_v2_generated_image": 8,
        "generated_image": 8,
    }.get(artifact_type, 5)
    return (priority, str(artifact.get("created_at") or ""))


def _delivery_acceptance(office_id: str, artifacts: list[dict]) -> dict:
    if office_id != "comic_production":
        return {}

    word = _latest_artifact(artifacts, {"comic_v2_word_canvas", "word_canvas"})
    handoff = _latest_artifact(artifacts, {"comic_v2_handoff_manifest"})
    source = handoff or word or {}
    metadata = source.get("metadata") or {}
    benchmark = metadata.get("quality_benchmark") or {}
    prompt_summary = benchmark.get("prompt_quality_summary") or {}
    image_summary = benchmark.get("image_quality_summary") or {}
    recovery_action = _delivery_recovery_action(benchmark)

    if not word and not handoff:
        return {
            "status": "waiting_for_delivery",
            "title": "交付验收",
            "summary": "还没有生成 Word 制片画布和引用清单。",
            "can_handoff_to_downstream": False,
            "can_claim_real_quality": False,
            "quality_score": 0,
            "visual_evidence_level": "",
            "acceptance_items": _acceptance_items(False, False, False, False),
            "missing_evidence": [
                "礼部：缺少 Word 制片画布。",
                "礼部 / 刑部：缺少引用清单和结构审计结果。",
            ],
            "next_action": "继续完成制片流程，生成 Word 制片画布和引用清单。",
            "recovery_action": {},
            "downloads": {},
        }

    has_word = bool(word)
    has_handoff = bool(handoff)
    has_benchmark = bool(benchmark)
    package_ready = bool(benchmark.get("package_quality_ready"))
    real_quality = bool(benchmark.get("production_quality_verified"))
    prompt_ready = (
        prompt_summary.get("status") == "ready"
        and int(prompt_summary.get("issue_count") or 0) == 0
    )
    total_images = int(image_summary.get("total_images") or 0)
    usable_images = int(image_summary.get("usable_images") or 0)
    rework_images = int(image_summary.get("waste_or_rework_images") or 0)
    images_ready = total_images > 0 and usable_images >= total_images and rework_images == 0

    if has_word and has_handoff and package_ready and real_quality:
        status = "ready_for_downstream"
        summary = "这份制片包已经具备下游生产交接条件，并且有真实质量验证证据。"
        next_action = "下载 Word 制片画布和引用清单，交给下游视频生成平台继续生产。"
    elif has_word and has_handoff and package_ready:
        status = "structure_ready_needs_real_quality"
        summary = "结构已经能交接，但只能说明制片包结构完整，暂不能宣称真实画质已验证。"
        next_action = "用真实模型重跑图片、执行视觉复核，再刷新 Word 画布和引用清单。"
    elif has_word or has_handoff:
        status = "needs_rework"
        summary = "已经有交付文件，但质量证据或引用链路还不完整。"
        next_action = "按缺失证据退回对应部门，重新生成后再交付。"
    else:
        status = "waiting_for_delivery"
        summary = "还没有可验收的最终交付。"
        next_action = "继续生成 Word 制片画布和引用清单。"

    missing = []
    if not has_word:
        missing.append("礼部：缺少 Word 制片画布。")
    if not has_handoff:
        missing.append("礼部 / 刑部：缺少引用清单，无法核对图片、镜头和提示词引用关系。")
    if not has_benchmark:
        missing.append("刑部：缺少制片包质量基准。")
    if has_benchmark and not prompt_ready:
        missing.append("兵部 / 刑部：提示词还存在泛化、串戏或导演信息不足的问题。")
    if has_benchmark and not images_ready:
        if total_images <= 0:
            missing.append("工部：缺少基础资产图片质量记录。")
        else:
            missing.append(f"工部 / 刑部：{rework_images} 张图片需要返工或复核。")
    if has_benchmark and not real_quality:
        missing.append("刑部：缺少真实模型视觉复核证据，不能公开宣称真实画质已验证。")

    return {
        "status": status,
        "title": "交付验收",
        "summary": summary,
        "can_handoff_to_downstream": status == "ready_for_downstream",
        "can_claim_real_quality": real_quality,
        "quality_score": int(benchmark.get("package_quality_score") or 0),
        "visual_evidence_level": str(benchmark.get("visual_evidence_level") or ""),
        "acceptance_items": _acceptance_items(
            has_word,
            has_handoff,
            prompt_ready,
            images_ready,
            package_ready=package_ready,
            real_quality=real_quality,
        ),
        "missing_evidence": missing,
        "next_action": next_action,
        "recovery_action": recovery_action,
        "downloads": {
            "word_canvas_uri": str((word or {}).get("uri") or ((word or {}).get("metadata") or {}).get("download_uri") or ""),
            "handoff_manifest_uri": str((handoff or {}).get("uri") or ((handoff or {}).get("metadata") or {}).get("download_uri") or ""),
        },
        "prompt_quality_summary": {
            "status": str(prompt_summary.get("status") or ""),
            "issue_count": int(prompt_summary.get("issue_count") or 0),
            "asset_prompt_count": int(prompt_summary.get("asset_prompt_count") or 0),
            "shot_prompt_count": int(prompt_summary.get("shot_prompt_count") or 0),
        },
        "image_quality_summary": {
            "total_images": total_images,
            "usable_images": usable_images,
            "waste_or_rework_images": rework_images,
        },
    }


def _delivery_recovery_action(benchmark: dict) -> dict:
    if not benchmark:
        return {}
    raw = benchmark.get("recommended_recovery") or {}
    if not raw and benchmark.get("package_quality_ready") is True and benchmark.get("production_quality_verified") is not True:
        raw = {
            "department": "工部 / 刑部",
            "action": "regenerate_images",
            "label": "用真实模型重跑并质检图片",
            "reason_code": "real_quality.evidence_missing",
            "description": "当前结构已通过，但缺少真实模型图片和视觉复核证据。",
            "expected_stage": "image_generation",
            "preserves": ["confirmed_story", "story_contract", "asset_manifest", "prompt_package"],
            "clears": ["image_production", "visual_review", "word_canvas", "handoff_manifest"],
            "operator_steps": [
                "确认工部图片模型和刑部视觉模型已配置。",
                "重新生成基础资产图片，并让刑部完成视觉复核。",
                "复核通过后重新生成 Word 制片画布和引用清单。",
            ],
        }
    if not isinstance(raw, dict):
        return {}
    if not str(raw.get("action") or "").strip():
        return {}
    return {
        "department": str(raw.get("department") or ""),
        "action": str(raw.get("action") or ""),
        "label": str(raw.get("label") or "按质量问题退回处理"),
        "reason_code": str(raw.get("reason_code") or ""),
        "description": str(raw.get("description") or ""),
        "expected_stage": str(raw.get("expected_stage") or ""),
        "preserves": [str(item) for item in (raw.get("preserves") or []) if str(item).strip()],
        "clears": [str(item) for item in (raw.get("clears") or []) if str(item).strip()],
        "operator_steps": [str(item) for item in (raw.get("operator_steps") or []) if str(item).strip()],
    }


def _latest_artifact(artifacts: list[dict], artifact_types: set[str]) -> dict:
    matches = [
        artifact
        for artifact in artifacts
        if str(artifact.get("artifact_type") or "") in artifact_types
    ]
    return matches[-1] if matches else {}


def _acceptance_items(
    has_word: bool,
    has_handoff: bool,
    prompt_ready: bool,
    images_ready: bool,
    *,
    package_ready: bool = False,
    real_quality: bool = False,
) -> list[dict]:
    return [
        {
            "id": "word_canvas",
            "label": "Word 制片画布",
            "passed": has_word,
            "owner": "礼部",
            "message": "最终画布可下载" if has_word else "还没有最终 Word 文件",
        },
        {
            "id": "handoff_manifest",
            "label": "引用清单",
            "passed": has_handoff,
            "owner": "礼部 / 刑部",
            "message": "资产、图片、镜头和提示词可追溯" if has_handoff else "还不能核对引用关系",
        },
        {
            "id": "prompt_quality",
            "label": "导演提示词",
            "passed": prompt_ready,
            "owner": "兵部 / 刑部",
            "message": "提示词可交给下游执行" if prompt_ready else "提示词还需要审校",
        },
        {
            "id": "image_quality",
            "label": "基础资产图片",
            "passed": images_ready,
            "owner": "工部 / 刑部",
            "message": "图片质量记录通过" if images_ready else "图片仍有缺口或返工项",
        },
        {
            "id": "package_quality",
            "label": "制片包质量基准",
            "passed": package_ready,
            "owner": "刑部",
            "message": "结构质量已通过" if package_ready else "制片包质量基准未通过",
        },
        {
            "id": "real_quality_claim",
            "label": "真实质量声明",
            "passed": real_quality,
            "owner": "刑部",
            "message": "可声明真实质量已验证" if real_quality else "不能宣称真实画质已验证",
        },
    ]


def _stage_lanes(office) -> list[dict]:
    lanes = []
    for checkpoint in office.human_checkpoints:
        lanes.append(
            {
                "id": checkpoint.get("id", ""),
                "title": checkpoint.get("title", ""),
                "owner": checkpoint.get("owner", ""),
                "kind": "human_checkpoint",
                "required": bool(checkpoint.get("required")),
            }
        )
    for action in enriched_recovery_actions(office.id):
        lanes.append(
            {
                "id": action.get("stage", ""),
                "title": action.get("label", ""),
                "owner": "",
                "kind": "recoverable_stage",
                "required": False,
            }
        )
    return lanes


def _next_action(active_task: dict, office, artifacts: list[dict]) -> str:
    if active_task:
        recovery = active_task.get("recovery_plan") or {}
        if recovery.get("recoverable"):
            return str(recovery.get("next_action") or "根据恢复动作从失败阶段继续。")
        status = active_task.get("status")
        if status in {"queued", "running"}:
            return "等待当前任务继续执行，必要时查看任务时间线确认哪个 Agent 正在工作。"
        if status == "completed":
            return "检查产物完成度，下载交付物或补齐缺失产物。"
    if artifacts:
        return "已有部分产物，优先检查缺失列表并从对应办公室阶段继续。"
    if office.human_checkpoints:
        first = office.human_checkpoints[0]
        return f"先完成「{first.get('title', '第一个人工审核节点')}」。"
    return "从工作台提交任务开始。"
