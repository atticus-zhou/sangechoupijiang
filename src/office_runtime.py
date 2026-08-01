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
        "artifact_progress": _artifact_progress(office.artifact_types, artifacts),
        "downloadable_artifacts": _downloadable_artifacts(artifacts),
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


def _artifact_progress(expected_types: list[str], artifacts: list[dict]) -> dict:
    by_type: dict[str, list[dict]] = {}
    for artifact in artifacts:
        by_type.setdefault(str(artifact.get("artifact_type") or ""), []).append(artifact)

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
    return downloadable


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
