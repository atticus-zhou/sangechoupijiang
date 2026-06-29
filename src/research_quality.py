"""Quality checks for research-office artifact packages."""

from __future__ import annotations

import re


REQUIRED_ARTIFACTS = {
    "report",
    "standard_report",
    "briefing",
    "source_list",
    "data_table",
    "competitor_table",
    "review_pain_points",
    "opportunity_map",
    "chart_plan",
    "screenshot_plan",
}


def assess_research_package(artifacts: list[dict]) -> dict:
    types = {a.get("artifact_type") for a in artifacts}
    missing = sorted(REQUIRED_ARTIFACTS - types)
    warnings: list[str] = []

    report_text = "\n\n".join(
        a.get("content", "")
        for a in artifacts
        if a.get("artifact_type") == "report"
    )
    standard_report_text = "\n\n".join(
        a.get("content", "")
        for a in artifacts
        if a.get("artifact_type") == "standard_report"
    )
    source_text = "\n\n".join(
        a.get("content", "")
        for a in artifacts
        if a.get("artifact_type") == "source_list"
    )

    if re.search(r"\bX\b|Y亿元|X百万|待补充|TODO", report_text, re.IGNORECASE):
        warnings.append("报告中可能仍有占位符或待补充内容。")
    if "[API错误]" in report_text or "AuthenticationError" in report_text or "Incorrect API key" in report_text:
        warnings.append("最终报告包含模型 API 错误，不能作为正式报告。")
    if "无截图任务触发" in report_text or "未使用browser_capture" in report_text or "未直接访问飞瓜" in report_text:
        warnings.append("报告声称未使用截图/飞瓜证据，需要核对证据链是否已注入。")
    if "暂未形成结构化来源清单" in source_text:
        warnings.append("来源清单仍是兜底提示，兵部需要输出结构化来源。")
    if "待识别" in source_text:
        warnings.append("仍有截图证据未完成视觉识别。")
    if len(report_text) < 800:
        warnings.append("报告正文偏短，可能不足以提交。")
    if not any(a.get("artifact_type") == "competitor_table" for a in artifacts):
        warnings.append("缺少竞品分析表，开品决策依据不足。")
    if not any(a.get("artifact_type") == "review_pain_points" for a in artifacts):
        warnings.append("缺少差评痛点分析，产品避坑依据不足。")
    if not any(a.get("artifact_type") == "opportunity_map" for a in artifacts):
        warnings.append("缺少差异化机会表，产品规划指向不足。")

    required_sections = (
        "## 行业概览",
        "## 竞品对比",
        "## 价格带与数据要点",
        "## 用户痛点",
        "## 差异化机会",
        "## 风险与建议",
        "## 证据与待核验",
    )
    missing_sections = [section for section in required_sections if section not in standard_report_text]
    if missing_sections:
        warnings.append("标准报告缺少必要章节：" + "、".join(missing_sections))
    if standard_report_text and "来源清单" not in standard_report_text:
        warnings.append("标准报告缺少来源清单引用。")
    if standard_report_text and "截图清单" not in standard_report_text:
        warnings.append("标准报告缺少截图清单引用。")

    score = 100
    score -= len(missing) * 12
    score -= len(warnings) * 10
    score = max(0, min(100, score))

    if score >= 80:
        status = "ready"
    elif score >= 55:
        status = "needs_review"
    else:
        status = "incomplete"

    return {
        "status": status,
        "score": score,
        "missing_artifacts": missing,
        "warnings": warnings,
    }
