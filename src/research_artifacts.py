"""Build research-office artifacts from a completed task result."""

from __future__ import annotations

import re

from src.research_office.output_schemas import (
    ResearchOutputSchemaError,
    validate_research_output_schema,
)


_SCHEMA_BY_ARTIFACT_TYPE = {
    "standard_report": "research_standard_report",
    "source_list": "research_source_list",
    "data_table": "research_data_table",
    "competitor_table": "research_competitor_table",
}


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
    research_plan = _make_research_plan(plan, results, report)
    if research_plan:
        artifacts.append({
            "artifact_type": "research_plan",
            "title": f"{title} - 调研计划",
            "content": research_plan,
            "metadata": {"source": "plan"},
            "created_by": "zhongshu",
        })

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

    evidence_gap_cards = _make_evidence_gap_cards(results, report)
    if evidence_gap_cards:
        artifacts.append({
            "artifact_type": "evidence_gap_cards",
            "title": f"{title} - 证据补齐卡",
            "content": evidence_gap_cards,
            "metadata": {"source": "evidence_gap_audit"},
            "created_by": "xingbu",
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

    standard_report = _make_standard_report(title, report, artifacts)
    if standard_report:
        artifacts.append({
            "artifact_type": "standard_report",
            "title": f"{title} - 标准调研报告",
            "content": standard_report,
            "metadata": {"source": "standard_template"},
            "created_by": "gongbu",
        })

    schema_gate_results = _apply_research_schema_gates(artifacts)
    if _has_schema_gate_failures(schema_gate_results):
        artifacts.append(_make_schema_gate_quality_report(title, schema_gate_results))

    for index, artifact in enumerate(artifacts, start=1):
        artifact["artifact_id"] = f"art_{task_id}_{artifact['artifact_type']}_{index}"
        artifact["task_id"] = task_id
    return artifacts


def _apply_research_schema_gates(artifacts: list[dict]) -> list[dict]:
    gate_results: list[dict] = []
    for artifact in artifacts:
        schema_id = _SCHEMA_BY_ARTIFACT_TYPE.get(artifact.get("artifact_type"))
        if not schema_id:
            continue
        try:
            result = validate_research_output_schema(schema_id, {"content": artifact.get("content", "")})
        except ResearchOutputSchemaError as exc:
            result = {
                "office_id": "research",
                "schema_id": schema_id,
                "status": "failed",
                "reason": str(exc),
            }
        artifact.setdefault("metadata", {})["schema_gate"] = result
        gate_results.append({
            "artifact_type": artifact.get("artifact_type", ""),
            "title": artifact.get("title", ""),
            **result,
        })
    return gate_results


def _has_schema_gate_failures(gate_results: list[dict]) -> bool:
    return any(item.get("status") != "passed" for item in gate_results)


def _make_schema_gate_quality_report(title: str, gate_results: list[dict]) -> dict:
    failed = [item for item in gate_results if item.get("status") != "passed"]
    lines = [
        f"# {title} - Schema Gate 质量报告",
        "",
        "以下交付物还没有通过结构校验，暂时不建议直接作为老板可读报告交付。",
        "",
        "| 交付物 | Schema | 状态 | 原因 |",
        "| --- | --- | --- | --- |",
    ]
    for item in failed:
        lines.append(
            f"| {_cell(item.get('artifact_type', ''))} | {_cell(item.get('schema_id', ''))} | "
            f"{_cell(item.get('status', ''))} | {_cell(item.get('reason', 'needs review'))} |"
        )
    return {
        "artifact_type": "quality_report",
        "title": f"{title} - Schema Gate 质量报告",
        "content": "\n".join(lines),
        "metadata": {
            "source": "schema_gate",
            "schema_gate": {
                "status": "needs_review",
                "failed_count": len(failed),
                "failed_schema_ids": [item.get("schema_id", "") for item in failed],
            },
        },
        "created_by": "xingbu",
    }


def _make_research_plan(plan: dict, results: list[dict], report: str) -> str:
    title = _strip_markdown(plan.get("title") or "调研项目")
    goal = _strip_markdown(plan.get("goal") or plan.get("objective") or "")
    user_request = _strip_markdown(plan.get("user_request") or plan.get("request") or "")

    step_lines = []
    for step in plan.get("steps", []) or []:
        if isinstance(step, dict):
            label = step.get("name") or step.get("title") or step.get("step_id") or "调研步骤"
            detail = step.get("goal") or step.get("description") or step.get("task") or ""
            step_lines.append(f"- {_cell(label)}：{_cell(detail)}")
        elif step:
            step_lines.append(f"- {_cell(str(step))}")

    evidence_targets = []
    for step in results:
        for source in step.get("sources", []) or []:
            if isinstance(source, dict):
                target = source.get("title") or source.get("url")
                if target:
                    evidence_targets.append(_cell(target))
        for ref in step.get("context_refs", []) or []:
            if ref:
                evidence_targets.append(_cell(str(ref)))

    if not step_lines:
        step_lines = [
            "- 明确调研目标、交付用途和老板真正要判断的问题。",
            "- 收集行业公开资料、平台数据、竞品信息、评论痛点和价格带。",
            "- 将数据、截图、来源链接和待核验项拆成可追溯证据。",
            "- 输出报告、老板摘要、数据表、竞品表、截图清单和机会判断。",
        ]

    if not evidence_targets:
        evidence_targets = [
            "平台搜索结果页、商品榜、品牌榜、达人榜或商品详情页截图",
            "行业报告、公开新闻、官方资料或电商页面来源截图",
        ]

    report_hint = ""
    if report:
        first_line = next((_strip_markdown(line) for line in report.splitlines() if _strip_markdown(line)), "")
        if first_line:
            report_hint = f"\n## 已有阶段结论\n- {first_line[:180]}"

    return "\n".join([
        f"# {title} - 调研计划",
        "",
        "## 调研目标",
        goal or user_request or "围绕用户提交的研究对象，形成可供职场汇报和开品判断使用的阶段性调研包。",
        "",
        "## 执行步骤",
        *step_lines[:8],
        "",
        "## 证据与截图计划",
        "截图不是一键全自动承诺；系统会在用户完成第三方平台登录、账号权限允许且页面可访问时辅助截图。无法访问的页面必须标记为待补证据。",
        *[f"- {item}" for item in evidence_targets[:10]],
        "",
        "## 交付物",
        "- 调研报告、老板摘要、数据要点表、竞品分析表、评论痛点表、机会地图、来源清单和截图清单。",
        "- 若飞瓜、抖音或电商后台权限不足，仍需输出阶段性结论、缺口说明和下一步补证路径。",
        report_hint,
    ]).strip()


def _make_standard_report(title: str, report: str, artifacts: list[dict]) -> str:
    by_type = {item.get("artifact_type"): item.get("content", "") for item in artifacts}
    source_list = by_type.get("source_list", "")
    data_table = by_type.get("data_table", "")
    competitor_table = by_type.get("competitor_table", "")
    pain_points = by_type.get("review_pain_points", "")
    opportunity_map = by_type.get("opportunity_map", "")
    screenshot_plan = by_type.get("screenshot_plan", "")
    evidence_gap_cards = by_type.get("evidence_gap_cards", "")

    industry = _pick_section(report, ("行业", "市场", "规模", "趋势"), fallback_chars=420)
    risk_lines = _collect_lines(report, ("风险", "建议", "结论", "待核验", "权限", "来源"))
    risk_text = "\n".join(f"- {line}" for line in risk_lines[:6]) or "- 关键结论需要继续用来源清单、截图证据和平台数据复核。"

    return "\n".join([
        f"# {title} - 标准调研报告",
        "",
        "## 行业概览",
        industry or "暂无完整行业概览。请补充市场规模、增长趋势、渠道变化和行业背景。",
        "",
        "## 竞品对比",
        competitor_table or "暂无结构化竞品表。请补充头部竞品、品牌、价格、卖点、用户和差评痛点。",
        "",
        "## 价格带与数据要点",
        data_table or "暂无结构化数据表。请补充价格带、销量、评价量、时间范围、来源和可信度。",
        "",
        "## 用户痛点",
        pain_points or "暂无评论痛点表。请补充好评关键词、差评原文、问题类型和产品机会。",
        "",
        "## 差异化机会",
        opportunity_map or "暂无机会地图。请基于竞品空位、评论痛点和渠道趋势整理差异化机会。",
        "",
        "## 风险与建议",
        risk_text,
        "",
        "## 证据与待核验",
        "来源清单：",
        source_list or "暂无来源清单，需要兵部补充来源 URL、发布日期、机构和可信度。",
        "",
        "截图清单：",
        screenshot_plan or "暂无截图清单，需要补充平台页面、榜单页或商品详情页截图目标。",
        "",
        "补证卡：",
        evidence_gap_cards or "暂无补证卡。请将待核验数据、截图缺口和权限缺口拆成可执行补证任务。",
    ]).strip()


def _pick_section(report: str, keywords: tuple[str, ...], fallback_chars: int = 400) -> str:
    lines = _collect_lines(report, keywords)
    if lines:
        return "\n".join(f"- {line}" for line in lines[:6])
    clean = _strip_markdown(report)
    return clean[:fallback_chars]


def _collect_lines(report: str, keywords: tuple[str, ...]) -> list[str]:
    lines = []
    for line in report.splitlines():
        clean = _strip_markdown(line)
        if clean and any(keyword in clean for keyword in keywords):
            lines.append(clean)
    return lines


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


def _make_evidence_gap_cards(results: list[dict], report: str) -> str:
    cards = _collect_evidence_gap_cards(results, report)
    rows = [
        "| 补证卡 | 负责人 | 需要补什么 | 为什么需要 | 建议文件名 | 验收标准 | 补完升级 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for card in cards:
        rows.append(
            f"| {_cell(card['title'])} | {_cell(card['owner'])} | {_cell(card['target_evidence'])} | "
            f"{_cell(card['why_needed'])} | {_cell(card['file_name'])} | {_cell(card['acceptance'])} | "
            f"{_cell(card['upgrades'])} |"
        )
    return "\n".join(rows)


def _collect_evidence_gap_cards(results: list[dict], report: str) -> list[dict]:
    cards: list[dict] = []

    pending_sources = _collect_pending_sources(results)
    for index, item in enumerate(pending_sources[:4], start=1):
        cards.append({
            "title": item.get("title") or f"来源页面补证 {index}",
            "owner": "兵部 / 人类操作者",
            "target_evidence": item.get("target_evidence") or item.get("url") or "来源页面 URL、页面截图和发布时间。",
            "why_needed": item.get("why_needed") or item.get("note") or "把报告中的来源线索升级为可追溯证据。",
            "file_name": f"evidence_{len(cards) + 1:02d}_source_page.png",
            "acceptance": "截图能看清页面标题、平台、时间范围或发布方；敏感账号信息已遮挡。",
            "upgrades": "来源清单、标准报告、老板摘要",
        })

    if _needs_price_or_data_evidence(results, report):
        cards.append({
            "title": "补齐价格带和关键数据截图",
            "owner": "户部 / 人类操作者",
            "target_evidence": "平台榜单、商品详情页、销量/热度/价格区间截图或导出表。",
            "why_needed": "把待核验价格、销量、规模或热度判断升级成老板可引用的数据表。",
            "file_name": f"evidence_{len(cards) + 1:02d}_price_or_metric.png",
            "acceptance": "每个数字能对应平台、时间范围、商品或榜单口径；无法确认的数字继续标记待核验。",
            "upgrades": "数据要点表、价格带图表、开品建议",
        })

    if _needs_competitor_evidence(results):
        cards.append({
            "title": "补齐 TOP 竞品矩阵",
            "owner": "户部 / 兵部",
            "target_evidence": "TOP 商品、品牌、价格、卖点、销量/热度、评论入口截图或表格。",
            "why_needed": "避免竞品表停留在占位描述，形成可比较的产品和品牌矩阵。",
            "file_name": f"evidence_{len(cards) + 1:02d}_competitor_ranking.png",
            "acceptance": "至少包含产品名称、品牌、价格或热度信号，并能对应一张截图或来源链接。",
            "upgrades": "竞品分析表、机会地图、风险与建议",
        })

    if _needs_review_evidence(report):
        cards.append({
            "title": "补齐评论痛点原始截图",
            "owner": "刑部 / 人类操作者",
            "target_evidence": "商品评论区、达人评论区、测评页或售后反馈截图。",
            "why_needed": "验证差评痛点是否真实高频，避免凭常识写产品机会。",
            "file_name": f"evidence_{len(cards) + 1:02d}_review_pain_points.png",
            "acceptance": "每类痛点至少有一条可读原文、平台位置和采集时间；隐私信息已遮挡。",
            "upgrades": "评论痛点表、差异化机会、风险提示",
        })

    if not cards:
        cards.append({
            "title": "人工复核关键结论",
            "owner": "刑部 / 人类操作者",
            "target_evidence": "复核报告中最关键的 3 条结论对应的来源、截图和数据口径。",
            "why_needed": "即使样例信息完整，正式交付前仍需要人工确认结论没有过期或误读。",
            "file_name": "evidence_01_final_review.png",
            "acceptance": "每条关键结论都有来源、截图或复核备注；不能确认的结论保留待核验标签。",
            "upgrades": "最终报告、交付声明、复核记录",
        })

    return cards


def _collect_pending_sources(results: list[dict]) -> list[dict]:
    pending: list[dict] = []
    seen = set()
    for step in results:
        for source in step.get("sources", []) or []:
            if not isinstance(source, dict):
                continue
            key = source.get("url") or source.get("title")
            if not key or key in seen:
                continue
            seen.add(key)
            pending.append({
                "title": source.get("title") or "来源页面",
                "url": source.get("url", ""),
                "note": source.get("note", ""),
                "target_evidence": source.get("url") or source.get("title") or "来源页面截图",
            })
        for ref in step.get("context_refs", []) or []:
            key = str(ref)
            if key and key not in seen:
                seen.add(key)
                pending.append({
                    "title": "来源页面",
                    "url": key,
                    "note": "作为关键来源证据",
                    "target_evidence": key,
                })
    return pending


def _needs_price_or_data_evidence(results: list[dict], report: str) -> bool:
    for step in results:
        for point in step.get("data_points", []) or []:
            if isinstance(point, dict):
                text = " ".join(str(point.get(key, "")) for key in ("value", "confidence", "note", "source_url"))
                if "待" in text or "pending" in text.lower() or not point.get("source_url"):
                    return True
    return bool(re.search(r"待核验|价格|销量|销售额|热度|市场规模|增长", report or ""))


def _needs_competitor_evidence(results: list[dict]) -> bool:
    competitors = []
    for step in results:
        competitors.extend([item for item in step.get("competitors", []) or [] if isinstance(item, dict)])
    if not competitors:
        return True
    return any(
        "待" in " ".join(str(item.get(key, "")) for key in ("sales", "price", "brand", "product_name"))
        for item in competitors
    )


def _needs_review_evidence(report: str) -> bool:
    return bool(re.search(r"差评|评论|痛点|售后|不满意|风险|投诉", report or ""))


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
