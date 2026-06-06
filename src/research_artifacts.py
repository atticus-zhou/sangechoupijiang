"""Build research-office artifacts from a completed task result."""

from __future__ import annotations

import re


def build_research_artifacts(task_id: str, result: dict) -> list[dict]:
    """Create normalized artifacts for the research office.

    The current engine may return one large report plus step summaries. This
    helper turns that into a small workplace package so the office UI has
    useful materials to organize even before richer agents exist.
    """
    report = result.get("final_report", "") or ""
    plan = result.get("plan", {}) or {}
    title = plan.get("title") or "Research report"
    results = result.get("results", []) or []

    artifacts: list[dict] = []
    if report:
        artifacts.append({
            "artifact_type": "report",
            "title": title,
            "content": report,
            "metadata": {"source": "final_report"},
            "created_by": "gongbu",
        })

        briefing = _make_briefing(report)
        if briefing:
            artifacts.append({
                "artifact_type": "briefing",
                "title": f"{title} - 老板摘要",
                "content": briefing,
                "metadata": {"source": "final_report"},
                "created_by": "libu_comm",
            })

        chart_plan = _make_chart_plan(report, results)
        if chart_plan:
            artifacts.append({
                "artifact_type": "chart_plan",
                "title": f"{title} - 图表建议",
                "content": chart_plan,
                "metadata": {"source": "final_report"},
                "created_by": "gongbu",
            })

    source_list = _make_source_list(results)
    if source_list:
        artifacts.append({
            "artifact_type": "source_list",
            "title": f"{title} - 来源清单",
            "content": source_list,
            "metadata": {"source": "step_results"},
            "created_by": "bingbu",
        })

    screenshot_plan = _make_screenshot_plan(results)
    if screenshot_plan:
        artifacts.append({
            "artifact_type": "screenshot_plan",
            "title": f"{title} - 截图取证计划",
            "content": screenshot_plan,
            "metadata": {"source": "source_list"},
            "created_by": "libu_comm",
        })

    data_table = _make_data_table(results, report)
    if data_table:
        artifacts.append({
            "artifact_type": "data_table",
            "title": f"{title} - 数据要点表",
            "content": data_table,
            "metadata": {"source": "step_results"},
            "created_by": "hubu",
        })

    competitor_table = _make_competitor_table(results, report)
    if competitor_table:
        artifacts.append({
            "artifact_type": "competitor_table",
            "title": f"{title} - 竞品分析表",
            "content": competitor_table,
            "metadata": {"source": "playbook"},
            "created_by": "hubu",
        })

    pain_points = _make_review_pain_points(results, report)
    if pain_points:
        artifacts.append({
            "artifact_type": "review_pain_points",
            "title": f"{title} - 差评痛点表",
            "content": pain_points,
            "metadata": {"source": "playbook"},
            "created_by": "xingbu",
        })

    opportunity_map = _make_opportunity_map(report)
    if opportunity_map:
        artifacts.append({
            "artifact_type": "opportunity_map",
            "title": f"{title} - 差异化机会表",
            "content": opportunity_map,
            "metadata": {"source": "playbook"},
            "created_by": "zhongshu",
        })

    for index, artifact in enumerate(artifacts, start=1):
        artifact["artifact_id"] = f"art_{task_id}_{artifact['artifact_type']}_{index}"
        artifact["task_id"] = task_id
    return artifacts


def _make_briefing(report: str) -> str:
    paragraphs = [
        _strip_markdown(line)
        for line in re.split(r"\n\s*\n", report)
        if _strip_markdown(line)
    ]
    useful = [
        p for p in paragraphs
        if not p.startswith("{") and "decision" not in p[:80].lower()
    ]
    return "\n\n".join(useful[:4])[:1200]


def _make_chart_plan(report: str, results: list[dict]) -> str:
    structured = []
    for step in results:
        for item in step.get("chart_suggestions", []) or []:
            if isinstance(item, dict):
                structured.append(item)
    if structured:
        rows = [
            "| 图表 | 类型 | 用途 | 所需数据 |",
            "| --- | --- | --- | --- |",
        ]
        for item in structured[:8]:
            rows.append(
                f"| {_cell(item.get('title', '图表'))} | {_cell(item.get('chart_type', ''))} | "
                f"{_cell(item.get('purpose', ''))} | {_cell(item.get('data_needed', ''))} |"
            )
        return "\n".join(rows)

    keywords = ("市场规模", "份额", "价格", "趋势", "出货", "销售额", "增长", "品牌")
    candidates = []
    for line in report.splitlines():
        clean = _strip_markdown(line)
        if clean and any(k in clean for k in keywords):
            candidates.append(clean)
    if not candidates:
        return ""
    suggestions = [
        "| 图表 | 建议用途 | 可用信息 |",
        "| --- | --- | --- |",
    ]
    for i, item in enumerate(candidates[:6], start=1):
        suggestions.append(f"| 图表{i} | 展示关键趋势或对比 | {item[:120]} |")
    return "\n".join(suggestions)


def _make_source_list(results: list[dict]) -> str:
    structured_rows = []
    sources: list[str] = []
    for step in results:
        for source in step.get("sources", []) or []:
            if isinstance(source, dict):
                structured_rows.append(source)
        for ref in step.get("context_refs", []) or []:
            if ref and ref not in sources:
                sources.append(str(ref))
        notes = step.get("notes", "")
        for url in re.findall(r"https?://[^\s)\]]+", notes):
            if url not in sources:
                sources.append(url)
    if structured_rows:
        rows = [
            "| 来源 | 发布方 | 日期 | URL | 备注 |",
            "| --- | --- | --- | --- | --- |",
        ]
        seen = set()
        for item in structured_rows:
            url = item.get("url", "")
            key = url or item.get("title", "")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                f"| {_cell(item.get('title', ''))} | {_cell(item.get('publisher', ''))} | "
                f"{_cell(item.get('published_at', ''))} | {_cell(url)} | {_cell(item.get('note', ''))} |"
            )
        return "\n".join(rows)
    if not sources:
        return "暂未形成结构化来源清单。下一步需要让兵部把来源 URL、发布日期、机构名称单独输出。"
    return "\n".join(f"- {source}" for source in sources)


def _make_screenshot_plan(results: list[dict]) -> str:
    candidates = []
    for step in results:
        for source in step.get("sources", []) or []:
            if isinstance(source, dict) and source.get("url"):
                candidates.append({
                    "title": source.get("title", "来源页面"),
                    "url": source.get("url", ""),
                    "reason": source.get("note", "作为关键来源证据"),
                })
        for url in step.get("context_refs", []) or []:
            if url:
                candidates.append({
                    "title": "来源页面",
                    "url": str(url),
                    "reason": "作为关键来源证据",
                })
    if not candidates:
        return "暂未识别可截图来源。下一步需要兵部输出结构化来源 URL 后再生成截图计划。"

    rows = [
        "| 截图对象 | URL | 截图用途 | 建议文件名 |",
        "| --- | --- | --- | --- |",
    ]
    seen = set()
    for i, item in enumerate(candidates[:10], start=1):
        url = item["url"]
        if url in seen:
            continue
        seen.add(url)
        rows.append(
            f"| {_cell(item['title'])} | {_cell(url)} | {_cell(item['reason'])} | evidence_{i:02d}.png |"
        )
    return "\n".join(rows)


def _make_data_table(results: list[dict], report: str = "") -> str:
    structured_rows = []
    for step in results:
        for point in step.get("data_points", []) or []:
            if isinstance(point, dict):
                structured_rows.append(point)
    if structured_rows:
        rows = [
            "| 指标 | 数值 | 时间范围 | 可信度 | 来源 | 备注 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for point in structured_rows[:20]:
            rows.append(
                f"| {_cell(point.get('metric', ''))} | {_cell(point.get('value', ''))} | "
                f"{_cell(point.get('period', ''))} | {_cell(point.get('confidence', ''))} | "
                f"{_cell(point.get('source_url', ''))} | {_cell(point.get('note', ''))} |"
            )
        return "\n".join(rows)

    rows = [
        "| 步骤 | 部门 | 状态 | 数据/结论摘要 |",
        "| --- | --- | --- | --- |",
    ]
    for step in results:
        summary = step.get("summary") or step.get("output") or step.get("content") or ""
        if summary:
            rows.append(
                f"| {step.get('step_id', '')} | {step.get('department', '')} | "
                f"{step.get('status', '')} | {_strip_table_cell(summary)[:180]} |"
            )
    if len(rows) > 2:
        return "\n".join(rows)

    extracted = _extract_data_lines(report)
    if not extracted:
        return ""
    fallback_rows = [
        "| 指标/结论 | 数值 | 时间范围 | 可信度 | 来源 | 备注 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for line in extracted[:12]:
        fallback_rows.append(
            f"| {_cell(line[:80])} | 待核验 | 待核验 | 中 | 待补充 | 从报告正文抽取，需补来源 |"
        )
    return "\n".join(fallback_rows)


def _extract_data_lines(report: str) -> list[str]:
    patterns = (r"\d+(?:\.\d+)?%", r"\d+(?:\.\d+)?\s*亿", r"\d+(?:\.\d+)?\s*元", r"\d{4}年", r"CR\d")
    lines = []
    for line in report.splitlines():
        clean = _strip_markdown(line)
        if clean and any(re.search(pattern, clean) for pattern in patterns):
            lines.append(clean)
    return lines


def _make_competitor_table(results: list[dict], report: str) -> str:
    rows = [
        "| 产品名称 | 品牌 | 销售额/销量 | 单价/价格带 | 核心卖点 | 目标人群 | 好评关键词 | 差评痛点 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    found = False
    for step in results:
        for item in step.get("competitors", []) or []:
            if not isinstance(item, dict):
                continue
            found = True
            rows.append(
                f"| {_cell(item.get('product_name', ''))} | {_cell(item.get('brand', ''))} | "
                f"{_cell(item.get('sales', ''))} | {_cell(item.get('price', ''))} | "
                f"{_cell(item.get('selling_points', ''))} | {_cell(item.get('target_user', ''))} | "
                f"{_cell(item.get('positive_keywords', ''))} | {_cell(item.get('negative_pain_points', ''))} |"
            )
    if found:
        return "\n".join(rows)
    return (
        "| 产品名称 | 品牌 | 销售额/销量 | 单价/价格带 | 核心卖点 | 目标人群 | 好评关键词 | 差评痛点 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 待补充 | 待补充 | 待核验 | 待核验 | 从平台 Top 商品提取 | 待补充 | 待补充 | 待补充 |\n\n"
        "说明: 当前任务未形成结构化竞品表。需要兵部/户部基于平台 Top 商品补齐。"
    )


def _make_review_pain_points(results: list[dict], report: str) -> str:
    pain_keywords = ("差评", "痛点", "不满意", "物流", "品质", "效果差", "虚假", "性价比")
    lines = []
    for line in report.splitlines():
        clean = _strip_markdown(line)
        if clean and any(k in clean for k in pain_keywords):
            lines.append(clean)
    rows = [
        "| 问题类型 | 占比/条数 | 典型差评原文 | 产品机会 |",
        "| --- | --- | --- | --- |",
    ]
    if not lines:
        rows.append("| 待补充 | 待核验 | 待采集 | 需从评论区/评价数据提取 |")
    else:
        for item in lines[:8]:
            rows.append(f"| 待分类 | 待核验 | {_cell(item[:120])} | 围绕该痛点优化产品或表达 |")
    return "\n".join(rows)


def _make_opportunity_map(report: str) -> str:
    keywords = ("机会", "差异化", "建议", "避坑", "定位", "卖点", "策略")
    candidates = []
    for line in report.splitlines():
        clean = _strip_markdown(line)
        if clean and any(k in clean for k in keywords):
            candidates.append(clean)
    rows = [
        "| 机会点 | 当前覆盖率 | 机会分析 |",
        "| --- | --- | --- |",
    ]
    if not candidates:
        rows.append("| 待补充 | 待核验 | 需要结合竞品和差评数据提炼差异化机会 |")
    else:
        for item in candidates[:8]:
            rows.append(f"| {_cell(item[:40])} | 待核验 | {_cell(item[:160])} |")
    return "\n".join(rows)


def _strip_markdown(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"^#+\s*", "", text)
    text = text.replace("**", "").replace("`", "")
    return text.strip()


def _strip_table_cell(text: str) -> str:
    return _strip_markdown(text).replace("|", "/").replace("\n", " ")


def _cell(text: str) -> str:
    return _strip_table_cell(text or "")
