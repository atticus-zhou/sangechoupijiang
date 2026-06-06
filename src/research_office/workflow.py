"""Research-office workflow rules and fallback report helpers."""

from __future__ import annotations

import re
from collections.abc import Callable


def research_capture_keyword(user_request: str) -> str:
    """Extract a product/category keyword from a research-office request."""
    patterns = [
        r"研究对象[:：]\s*([^\n，,。；;]+)",
        r"开品调研[：:\s]*([^\n，,。；;]+)",
        r"调研[：:\s]*([^\n，,。；;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_request)
        if match:
            value = match.group(1).strip()
            if value:
                return value[:60]
    first_line = (user_request or "").strip().splitlines()[0] if (user_request or "").strip() else ""
    return first_line[:60]


def needs_platform_evidence(user_request: str, office_id: str) -> bool:
    if office_id != "research":
        return False
    text = user_request or ""
    keywords = ("飞瓜", "抖音", "内容电商", "电商平台", "榜单", "截图", "取证", "开品", "选品", "竞品")
    return any(k in text for k in keywords)


def format_workspace_evidence_context(
    artifacts: list[dict],
    max_chars: int = 6000,
) -> str:
    """Build compact evidence context for the report-writing agents."""
    relevant_types = {
        "screenshot_evidence",
        "screenshot_extraction",
        "source_list",
        "data_table",
        "competitor_table",
        "quality_report",
    }
    chunks = ["【工作区截图证据上下文】"]
    for artifact in artifacts:
        if artifact.get("artifact_type") not in relevant_types:
            continue
        title = artifact.get("title", "")
        artifact_type = artifact.get("artifact_type", "")
        uri = artifact.get("uri", "")
        content = (artifact.get("content") or "").strip()
        if not content:
            continue
        chunks.append(f"\n### {artifact_type}: {title}")
        if uri:
            chunks.append(f"截图/来源: {uri}")
        chunks.append(content[:1200])
        if sum(len(c) for c in chunks) > max_chars:
            break
    return "\n".join(chunks)[:max_chars]


def build_evidence_fallback_result(
    task_id: str,
    workspace_id: str,
    user_request: str,
    artifacts: list[dict],
    reason: str = "fallback",
    keyword_extractor: Callable[[str], str] = research_capture_keyword,
) -> dict:
    """Create a usable research handoff when the full agent workflow stalls."""
    title = keyword_extractor(user_request) or "研究对象"
    by_type: dict[str, list[dict]] = {}
    for artifact in artifacts:
        by_type.setdefault(artifact.get("artifact_type", ""), []).append(artifact)

    def section_for(artifact_type: str, heading: str, limit: int = 2, chars: int = 1800) -> str:
        items = by_type.get(artifact_type, [])[:limit]
        if not items:
            return f"## {heading}\n\n暂无可用材料。"
        chunks = [f"## {heading}"]
        for item in items:
            content = (item.get("content") or "").strip()
            uri = item.get("uri") or ""
            chunks.append(f"\n### {item.get('title', artifact_type)}")
            if uri:
                chunks.append(f"来源: {uri}")
            chunks.append(content[:chars] if content else "暂无正文。")
        return "\n\n".join(chunks)

    screenshot_count = len(by_type.get("screenshot_evidence", []))
    extraction_count = len(by_type.get("screenshot_extraction", []))
    report = "\n\n".join([
        f"# {title}研究报告（证据版草稿）",
        (
            "本报告由研究办公室在完整 agent 工作流未能按时结束时自动生成，"
            "优先保留已经完成的飞瓜截图、视觉识别结果和证据表。"
        ),
        "## 当前状态",
        "\n".join([
            f"- 任务编号: {task_id}",
            f"- 生成原因: {reason}",
            f"- 已入库截图: {screenshot_count} 张",
            f"- 已完成视觉识别: {extraction_count} 条",
            "- 结论等级: 可作为内部核验草稿，不应直接当作最终老板汇报稿。",
        ]),
        section_for("source_list", "证据来源清单", limit=1, chars=2200),
        section_for("screenshot_extraction", "原始截图识别摘录", limit=2, chars=2200),
        section_for("data_table", "截图识别数据要点", limit=1, chars=2600),
        section_for("competitor_table", "竞品与对象线索", limit=1, chars=2600),
        section_for("review_pain_points", "痛点与风险", limit=1, chars=2200),
        section_for("opportunity_map", "机会与下一步动作", limit=1, chars=2200),
        section_for("screenshot_plan", "截图归档清单", limit=1, chars=2200),
        "## 需要人工确认或后续补强",
        "\n".join([
            "- 如果截图停留在入口页、说明页或榜单样例页，相关数据只能标为待核验。",
            "- 后续应让浏览器自动化进入具体商品榜、品牌榜、达人榜和详情页，而不是只截功能入口。",
            "- 最终 Word 报告需要把截图放回模板占位位置，并补充数据解读、图表和结论。",
        ]),
    ])
    return {
        "status": "completed",
        "task_id": task_id,
        "plan": {
            "title": f"{title}研究报告（证据版草稿）",
            "source": "evidence_fallback",
        },
        "final_report": report,
        "metadata": {
            "fallback": True,
            "fallback_reason": reason,
            "workspace_id": workspace_id,
            "screenshot_count": screenshot_count,
            "extraction_count": extraction_count,
        },
    }
