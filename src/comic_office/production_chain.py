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


def build_production_chain_state(
    package: dict,
    model_readiness: dict | None = None,
    asset_review_status: str = "",
) -> dict:
    """Return visible department status for a production package."""
    gate = build_production_quality_gate(package, model_readiness=model_readiness)
    departments = []
    review_pending = asset_review_status == "pending"
    review_returned = asset_review_status in {"revision_requested", "needs_revision"}
    for spec in DEPARTMENT_CHAIN:
        blocking = _department_blockers(spec["department_id"], package, gate)
        ui_status = "blocked" if blocking else "completed"
        if gate.get("status") == "waiting_for_human" and spec["department_id"] == "xingbu":
            ui_status = "waiting_for_human"
        if review_pending and spec["department_id"] == "menxia" and not blocking:
            ui_status = "waiting_for_human"
        if review_returned and spec["department_id"] in {"zhongshu", "menxia"} and not blocking:
            ui_status = "waiting_for_human"
        departments.append({
            **spec,
            "status": "blocked" if blocking else "completed",
            "ui_status": ui_status,
            "status_label": _department_status_label(ui_status),
            "blocking_issues": blocking,
            "human_checkpoint": _department_human_checkpoint(spec["department_id"], asset_review_status),
        })
    current_department, next_action, human_action_required = _current_chain_action(
        departments,
        gate,
        asset_review_status,
    )
    if review_returned:
        overall_status = "waiting_for_asset_revision"
    elif review_pending:
        overall_status = "waiting_for_asset_review"
    elif gate["status"] == "waiting_for_human":
        overall_status = "waiting_for_visual_review"
    else:
        overall_status = "ready_for_handoff" if gate["status"] == "passed" else "blocked"
    return {
        "project": package.get("title", ""),
        "script_hash": (package.get("script_binding") or {}).get("script_hash", ""),
        "script_version": (package.get("script_binding") or {}).get("script_version", 0),
        "overall_status": overall_status,
        "asset_review_status": asset_review_status,
        "current_department": current_department,
        "next_action": next_action,
        "human_action_required": human_action_required,
        "stage_summary": _stage_summary(overall_status, current_department, next_action),
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
    hard_visual_issues: list[str] = []
    review_issues: list[str] = []
    visual_scores: list[int] = []
    image_summary = package.get("image_quality_summary") or {}
    if image_summary:
        expected = int(image_summary.get("expected") or 0)
        generated = int(image_summary.get("generated") or 0)
        failed = int(image_summary.get("failed") or max(0, expected - generated))
        if failed:
            hard_visual_issues.append(f"{failed} image generation failures")
        elif generated < expected:
            hard_visual_issues.append(f"{expected - generated} generated images missing")
        reviews = image_summary.get("reviews") or []
        reviewed_ids = set()
        for review in reviews:
            source_id = str(review.get("source_id") or review.get("title") or "unknown image")
            reviewed_ids.add(source_id)
            status = str(review.get("status") or "needs_review")
            score_value = int(review.get("score") or 0)
            visual_scores.append(score_value)
            if status != "pass" or score_value < 80:
                review_issues.append(f"{source_id} visual review {status} score {score_value}")
        if generated > len(reviews):
            review_issues.append(f"{generated - len(reviews)} generated images missing visual review")
            visual_scores.extend([0] * (generated - len(reviews)))
    issues.extend(hard_visual_issues)
    issues.extend(review_issues)
    base_score = max(0, 100 - len(issues) * 15)
    visual_score = int(sum(visual_scores) / len(visual_scores)) if visual_scores else 100
    score = min(base_score, visual_score)
    status = "passed"
    if hard_visual_issues or any(issue not in review_issues for issue in issues):
        status = "blocked"
    elif review_issues:
        status = "waiting_for_human"
    return {
        "status": status,
        "score": score,
        "blocking_issues": issues,
        "image_quality_summary": image_summary,
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


def _current_chain_action(departments: list[dict], gate: dict, asset_review_status: str) -> tuple[str, str, bool]:
    if asset_review_status in {"revision_requested", "needs_revision"}:
        return (
            "中书省/门下省",
            "资产拆解已退回，请根据退回意见重新拆解人物、道具、场景和镜头输入。",
            True,
        )
    if asset_review_status == "pending":
        return (
            "门下省",
            "请先审核资产拆解包，确认人物、道具、场景和镜头输入后再继续生成图片与 Word 画布。",
            True,
        )
    if gate.get("status") == "waiting_for_human":
        return (
            "刑部",
            "部分图片尚未通过视觉检查，请人工复核低分或未审图片，通过或重生成后再交付。",
            True,
        )
    for dept in departments:
        if dept.get("blocking_issues"):
            return (
                dept.get("name", dept.get("department_id", "")),
                "请处理阻塞项：" + "；".join(dept.get("blocking_issues") or []),
                False,
            )
    if gate.get("status") == "passed":
        return ("礼部", "制片包已满足交付条件，可以下载 Word 画布或继续做质量复核。", False)
    return ("尚书省", "等待生产链补齐缺失材料。", False)


def _stage_summary(overall_status: str, current_department: str, next_action: str) -> str:
    labels = {
        "waiting_for_asset_review": "等待人工审核",
        "waiting_for_asset_revision": "等待重新拆解",
        "waiting_for_visual_review": "等待视觉审核",
        "ready_for_handoff": "可以交付",
        "blocked": "存在阻塞",
    }
    return f"{labels.get(overall_status, overall_status)}：{current_department} - {next_action}"


def _department_status_label(status: str) -> str:
    return {
        "completed": "已完成",
        "blocked": "阻塞",
        "waiting_for_human": "待人工确认",
    }.get(status, status)


def _department_human_checkpoint(department_id: str, asset_review_status: str) -> str:
    if asset_review_status in {"revision_requested", "needs_revision"} and department_id in {"zhongshu", "menxia"}:
        return "根据退回意见重新拆解资产清单，重新生成后再交给人审核。"
    if department_id == "menxia" and asset_review_status == "pending":
        return "审核资产拆解包：人物、道具、场景、镜头输入是否符合已确认故事。"
    if department_id == "gongbu":
        return "确认模型配置可用后生成基础资产、镜头参考图和 Word 画布。"
    if department_id == "xingbu":
        return "检查一致性、缺图、提示词漂移和可交付性。"
    return ""


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
