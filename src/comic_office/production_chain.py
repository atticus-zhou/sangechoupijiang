"""Department-level production chain state for the comic production office."""

from __future__ import annotations


DEPARTMENT_CHAIN = [
    {
        "department_id": "zhongshu",
        "name": "中书省",
        "depends_on": [],
        "inputs": ["confirmed_script", "memory_vault"],
        "outputs": ["production_brief"],
    },
    {
        "department_id": "menxia",
        "name": "门下省",
        "depends_on": ["zhongshu"],
        "inputs": ["production_brief"],
        "outputs": ["production_review"],
    },
    {
        "department_id": "shangshu",
        "name": "尚书省",
        "depends_on": ["menxia"],
        "inputs": ["production_review"],
        "outputs": ["dispatch_plan"],
    },
    {
        "department_id": "libu",
        "name": "吏部",
        "depends_on": ["shangshu"],
        "inputs": ["confirmed_script", "dispatch_plan"],
        "outputs": ["continuity_bible"],
    },
    {
        "department_id": "hubu",
        "name": "户部",
        "depends_on": ["shangshu"],
        "inputs": ["characters", "props", "scenes"],
        "outputs": ["asset_registry"],
    },
    {
        "department_id": "bingbu",
        "name": "兵部",
        "depends_on": ["libu", "hubu"],
        "inputs": ["script_beats", "asset_registry"],
        "outputs": ["shot_prompt_handoff"],
    },
    {
        "department_id": "gongbu",
        "name": "工部",
        "depends_on": ["bingbu"],
        "inputs": ["asset_registry", "shot_prompt_handoff"],
        "outputs": ["generated_image", "prompt_package", "word_canvas"],
    },
    {
        "department_id": "libu_comm",
        "name": "礼部",
        "depends_on": ["gongbu"],
        "inputs": ["word_canvas", "platform"],
        "outputs": ["platform_delivery_spec"],
    },
    {
        "department_id": "xingbu",
        "name": "刑部",
        "depends_on": ["gongbu", "libu_comm"],
        "inputs": ["all_outputs"],
        "outputs": ["quality_report"],
    },
]


def build_production_chain_state(package: dict, model_readiness: dict | None = None) -> dict:
    """Return visible department status for a production package."""
    gate = build_production_quality_gate(package, model_readiness=model_readiness)
    departments = []
    for spec in DEPARTMENT_CHAIN:
        blocking = _department_blockers(spec["department_id"], package, gate)
        departments.append({
            **spec,
            "status": "blocked" if blocking else "completed",
            "blocking_issues": blocking,
        })
    overall_status = "ready_for_handoff" if gate["status"] == "passed" else "blocked"
    return {
        "project": package.get("title", ""),
        "script_hash": (package.get("script_binding") or {}).get("script_hash", ""),
        "script_version": (package.get("script_binding") or {}).get("script_version", 0),
        "overall_status": overall_status,
        "quality_gate": gate,
        "departments": departments,
    }


def build_production_quality_gate(package: dict, model_readiness: dict | None = None) -> dict:
    """Score whether the production chain has enough material to hand off."""
    issues: list[str] = []
    binding = package.get("script_binding") or {}
    confirmed = package.get("confirmed_script") or {}
    if not binding.get("confirmed") and not confirmed:
        issues.append("confirmed script missing")
    if not (confirmed.get("story_draft") or (package.get("script_preview") or {}).get("story_draft")):
        issues.append("locked story draft missing")
    if not package.get("characters"):
        issues.append("character assets missing")
    if not package.get("props"):
        issues.append("prop assets missing")
    if not package.get("scenes"):
        issues.append("scene assets missing")
    shots = package.get("shots") or []
    if not shots:
        issues.append("shot prompts missing")
    else:
        if any(not shot.get("image_prompt") for shot in shots):
            issues.append("shot image prompts missing")
        if any(not shot.get("video_prompt") for shot in shots):
            issues.append("shot video prompts missing")
    for item in (model_readiness or {}).values():
        if not item.get("ready"):
            issues.append(str(item.get("detail") or "required model is not configured"))
    score = max(0, 100 - len(issues) * 15)
    return {
        "status": "passed" if not issues else "blocked",
        "score": score,
        "blocking_issues": issues,
    }


def format_production_chain_state(state: dict) -> str:
    """Render the chain state as a readable artifact."""
    lines = [
        "# 多 Agent 制片链状态",
        "",
        f"- 项目：{state.get('project', '')}",
        f"- 剧本版本：v{state.get('script_version', 0)}",
        f"- 剧本哈希：{state.get('script_hash', '')}",
        f"- 总状态：{state.get('overall_status', '')}",
        f"- 验收分：{(state.get('quality_gate') or {}).get('score', 0)}",
        "",
        "| 部门 | 状态 | 依赖 | 输入 | 输出 | 阻塞原因 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for dept in state.get("departments", []) or []:
        lines.append(
            f"| {dept.get('name', '')} | {dept.get('status', '')} | "
            f"{', '.join(dept.get('depends_on') or []) or '-'} | "
            f"{', '.join(dept.get('inputs') or [])} | "
            f"{', '.join(dept.get('outputs') or [])} | "
            f"{'; '.join(dept.get('blocking_issues') or []) or '-'} |"
        )
    issues = (state.get("quality_gate") or {}).get("blocking_issues") or []
    if issues:
        lines.extend(["", "## 刑部阻塞项", *[f"- {item}" for item in issues]])
    return "\n".join(lines)


def _department_blockers(department_id: str, package: dict, gate: dict) -> list[str]:
    issues = gate.get("blocking_issues") or []
    if department_id in {"zhongshu", "menxia", "shangshu"}:
        return [item for item in issues if "script" in item or "story" in item]
    if department_id == "hubu":
        return [item for item in issues if "asset" in item]
    if department_id == "bingbu":
        return [item for item in issues if "shot" in item]
    if department_id in {"gongbu", "libu_comm", "xingbu"}:
        return list(issues)
    return []
