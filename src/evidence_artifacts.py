"""Build standard research artifacts from screenshot evidence extractions."""

from __future__ import annotations

import json
import re
from typing import Any


def build_evidence_artifacts(workspace_id: str, artifacts: list[dict]) -> list[dict]:
    screenshots = [a for a in artifacts if a.get("artifact_type") == "screenshot_evidence"]
    extractions = [
        a for a in artifacts
        if a.get("artifact_type") == "screenshot_extraction"
        and (a.get("metadata") or {}).get("status") != "failed"
        and not (a.get("content") or "").strip().startswith("[API")
    ]
    parsed = [_parse_extraction(a) for a in extractions]

    result = [
        _artifact(
            workspace_id,
            "source_list",
            "截图证据来源清单",
            _make_source_list(screenshots, parsed),
            {"source": "screenshot_evidence", "screenshot_count": len(screenshots), "extraction_count": len(extractions)},
            "bingbu",
        ),
        _artifact(
            workspace_id,
            "screenshot_plan",
            "已上传截图证据清单",
            _make_screenshot_list(screenshots, parsed),
            {"source": "screenshot_evidence", "screenshot_count": len(screenshots)},
            "bingbu",
        ),
        _artifact(
            workspace_id,
            "data_table",
            "截图识别数据要点表",
            _make_data_table(parsed),
            {"source": "screenshot_extraction", "extraction_count": len(extractions)},
            "hubu",
        ),
        _artifact(
            workspace_id,
            "competitor_table",
            "截图识别竞品表",
            _make_competitor_table(parsed),
            {"source": "screenshot_extraction", "extraction_count": len(extractions)},
            "hubu",
        ),
        _artifact(
            workspace_id,
            "review_pain_points",
            "截图识别痛点表",
            _make_pain_points(parsed),
            {"source": "screenshot_extraction", "extraction_count": len(extractions)},
            "xingbu",
        ),
        _artifact(
            workspace_id,
            "opportunity_map",
            "截图识别机会表",
            _make_opportunity_map(parsed),
            {"source": "screenshot_extraction", "extraction_count": len(extractions)},
            "zhongshu",
        ),
        _artifact(
            workspace_id,
            "chart_plan",
            "截图数据图表建议",
            _make_chart_plan(parsed),
            {"source": "screenshot_extraction", "extraction_count": len(extractions)},
            "gongbu",
        ),
        _artifact(
            workspace_id,
            "quality_report",
            "截图证据验收报告",
            _make_quality_report(screenshots, parsed),
            _quality_metadata(screenshots, parsed),
            "xingbu",
        ),
    ]
    return [a for a in result if a.get("content")]


def _artifact(workspace_id: str, artifact_type: str, title: str, content: str, metadata: dict, created_by: str) -> dict:
    return {
        "artifact_id": f"art_{workspace_id}_evidence_{artifact_type}",
        "workspace_id": workspace_id,
        "task_id": "",
        "artifact_type": artifact_type,
        "title": title,
        "content": content,
        "metadata": metadata,
        "created_by": created_by,
    }


def _parse_extraction(artifact: dict) -> dict:
    content = artifact.get("content") or ""
    data = _loads_jsonish(content)
    if not isinstance(data, dict):
        data = {"raw_text": content}
    return {
        "artifact_id": artifact.get("artifact_id", ""),
        "title": artifact.get("title", ""),
        "uri": artifact.get("uri", ""),
        "metadata": artifact.get("metadata") or {},
        "data": data,
        "content": content,
    }


def _loads_jsonish(text: str) -> Any:
    clean = (text or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    candidates = [clean]
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _make_source_list(screenshots: list[dict], parsed: list[dict]) -> str:
    if not screenshots:
        return ""
    rows = [
        "| 证据 | 文件/来源 | 说明 | 识别状态 |",
        "| --- | --- | --- | --- |",
    ]
    extraction_by_source = {
        p["metadata"].get("source_artifact_id"): p for p in parsed
    }
    for shot in screenshots:
        meta = shot.get("metadata") or {}
        extraction = extraction_by_source.get(shot.get("artifact_id"))
        rows.append(
            "| {title} | {file} | {note} | {status} |".format(
                title=_cell(shot.get("title", "截图证据")),
                file=_cell(meta.get("original_filename") or shot.get("uri", "")),
                note=_cell(meta.get("note") or "用户上传截图"),
                status=_cell("已识别" if extraction else "待识别"),
            )
        )
    return "\n".join(rows)


def _make_screenshot_list(screenshots: list[dict], parsed: list[dict]) -> str:
    if not screenshots:
        return ""
    rows = [
        "| 截图 | 预览地址 | 用途 | 下一步 |",
        "| --- | --- | --- | --- |",
    ]
    extracted = {p["metadata"].get("source_artifact_id") for p in parsed}
    for shot in screenshots:
        rows.append(
            f"| {_cell(shot.get('title', '截图证据'))} | {_cell(shot.get('uri', ''))} | "
            f"平台数据取证 | {_cell('纳入数据表/竞品表' if shot.get('artifact_id') in extracted else '点击识别截图')} |"
        )
    return "\n".join(rows)


def _make_data_table(parsed: list[dict]) -> str:
    rows = [
        "| 指标 | 数值 | 场景/上下文 | 证据原文 | 可信度 | 来源截图 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    count = 0
    for item in parsed:
        data = item["data"]
        for point in _as_list(data.get("key_numbers")):
            if not isinstance(point, dict):
                continue
            count += 1
            rows.append(
                f"| {_cell(point.get('metric'))} | {_cell(point.get('value'))} | "
                f"{_cell(point.get('context'))} | {_cell(point.get('evidence_text'))} | "
                f"{_cell(point.get('confidence', '待核验'))} | {_cell(item.get('uri'))} |"
            )
        for table in _as_list(data.get("detected_tables")):
            for row in _rows_from_table(table):
                count += 1
                rows.append(
                    f"| {_cell(row.get('metric') or row.get('name') or row.get('product') or row.get('brand'))} | "
                    f"{_cell(row.get('value') or row.get('sales') or row.get('GMV') or row.get('price'))} | "
                    f"{_cell(row.get('rank') or row.get('source_text') or data.get('page_type'))} | "
                    f"{_cell(row.get('source_text'))} | {_cell(row.get('confidence', '待核验'))} | {_cell(item.get('uri'))} |"
                )
    if count:
        return "\n".join(rows)
    return "暂无可结构化的数据点。请先对截图执行识别，或上传更清晰的榜单/表格截图。"


def _make_competitor_table(parsed: list[dict]) -> str:
    rows = [
        "| 品牌 | 商品/对象 | 价格 | 销量/GMV | 卖点/结论 | 可信度 | 来源截图 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    count = 0
    for item in parsed:
        data = item["data"]
        for competitor in _as_list(data.get("competitors")):
            if not isinstance(competitor, dict):
                continue
            count += 1
            rows.append(
                f"| {_cell(competitor.get('brand'))} | {_cell(competitor.get('product') or competitor.get('name'))} | "
                f"{_cell(competitor.get('price'))} | {_cell(competitor.get('sales') or competitor.get('GMV'))} | "
                f"{_cell(competitor.get('claim') or competitor.get('selling_point'))} | "
                f"{_cell(competitor.get('confidence', '待核验'))} | {_cell(item.get('uri'))} |"
            )
    if count:
        return "\n".join(rows)
    return "暂无可结构化的竞品信息。请优先上传榜单、商品列表、详情页或评论页截图。"


def _make_pain_points(parsed: list[dict]) -> str:
    rows = [
        "| 痛点/风险 | 证据 | 影响 | 可信度 | 来源截图 |",
        "| --- | --- | --- | --- | --- |",
    ]
    count = 0
    for item in parsed:
        data = item["data"]
        pain_points = _as_list(data.get("pain_points") or data.get("review_pain_points"))
        for point in pain_points:
            count += 1
            if isinstance(point, dict):
                rows.append(
                    f"| {_cell(point.get('pain_point') or point.get('type') or point.get('issue'))} | "
                    f"{_cell(point.get('evidence_text') or point.get('quote'))} | {_cell(point.get('impact'))} | "
                    f"{_cell(point.get('confidence', '待核验'))} | {_cell(item.get('uri'))} |"
                )
            else:
                rows.append(f"| {_cell(point)} | 待核验 | 待评估 | 待核验 | {_cell(item.get('uri'))} |")
        for warning in _as_list(data.get("warnings")):
            count += 1
            rows.append(f"| {_cell(warning)} | 视觉识别提醒 | 影响数据可信度 | 待核验 | {_cell(item.get('uri'))} |")
    if count:
        return "\n".join(rows)
    return "暂无评论痛点或识别风险。请上传评论区、差评页或商品评价截图。"


def _make_opportunity_map(parsed: list[dict]) -> str:
    rows = [
        "| 机会/动作 | 来源 | 对产品/报告的意义 | 优先级 |",
        "| --- | --- | --- | --- |",
    ]
    count = 0
    for item in parsed:
        data = item["data"]
        opportunities = _as_list(data.get("opportunities") or data.get("recommended_next_steps"))
        for opportunity in opportunities:
            count += 1
            if isinstance(opportunity, dict):
                rows.append(
                    f"| {_cell(opportunity.get('opportunity') or opportunity.get('action') or opportunity.get('step'))} | "
                    f"{_cell(item.get('uri'))} | {_cell(opportunity.get('value') or opportunity.get('reason'))} | "
                    f"{_cell(opportunity.get('priority', '中'))} |"
                )
            else:
                rows.append(f"| {_cell(opportunity)} | {_cell(item.get('uri'))} | 可作为后续核验或产品规划动作 | 中 |")
    if count:
        return "\n".join(rows)
    return "暂无机会点。请先完成截图识别，或上传包含卖点、差评、价格带、榜单的截图。"


def _make_chart_plan(parsed: list[dict]) -> str:
    has_price = False
    has_sales = False
    has_competitors = False
    for item in parsed:
        data = item["data"]
        for competitor in _as_list(data.get("competitors")):
            if isinstance(competitor, dict):
                has_competitors = True
                has_price = has_price or bool(competitor.get("price"))
                has_sales = has_sales or bool(competitor.get("sales") or competitor.get("GMV"))
        for point in _as_list(data.get("key_numbers")):
            if isinstance(point, dict):
                metric = str(point.get("metric", ""))
                has_price = has_price or "价" in metric or "price" in metric.lower()
                has_sales = has_sales or "销" in metric or "sales" in metric.lower() or "GMV" in metric
    rows = [
        "| 图表 | 类型 | 数据来源 | 用途 | 状态 |",
        "| --- | --- | --- | --- | --- |",
    ]
    if has_competitors:
        rows.append("| 竞品对比矩阵 | table/matrix | 截图识别竞品表 | 对比品牌、商品、价格、销量和卖点 | 可生成 |")
    if has_price:
        rows.append("| 价格带分布 | bar | 截图识别数据要点表 | 判断民用无人机主流价格区间 | 可生成 |")
    if has_sales:
        rows.append("| 销量/GMV排行 | bar | 截图识别数据要点表 | 判断头部商品和品牌集中度 | 可生成 |")
    if len(rows) == 2:
        rows.append("| 证据覆盖状态 | checklist | 截图证据来源清单 | 展示哪些截图已识别、哪些待补 | 可生成 |")
    return "\n".join(rows)


def _make_quality_report(screenshots: list[dict], parsed: list[dict]) -> str:
    extracted = len(parsed)
    pending = max(0, len(screenshots) - extracted)
    lines = [
        f"状态: {'ready' if screenshots and pending == 0 else 'needs_review'}",
        f"截图数量: {len(screenshots)}",
        f"已识别: {extracted}",
        f"待识别: {pending}",
        "",
        "验收提醒:",
    ]
    if not screenshots:
        lines.append("- 还没有上传截图证据。")
    if pending:
        lines.append("- 仍有截图没有执行视觉识别，报告中的平台数据需要标为待核验。")
    if extracted:
        lines.append("- 已生成截图识别数据表和竞品表，后续可用于图表生成和报告引用。")
    lines.append("- 识别结果仍需保留原始截图链接，避免数据脱离证据。")
    return "\n".join(lines)


def _quality_metadata(screenshots: list[dict], parsed: list[dict]) -> dict:
    pending = max(0, len(screenshots) - len(parsed))
    return {
        "source": "screenshot_evidence",
        "status": "ready" if screenshots and pending == 0 else "needs_review",
        "score": 100 if screenshots and pending == 0 else max(30, 80 - pending * 15),
        "screenshot_count": len(screenshots),
        "extraction_count": len(parsed),
        "missing_artifacts": [],
        "warnings": ["仍有截图待识别"] if pending else [],
    }


def _rows_from_table(table: Any) -> list[dict]:
    if isinstance(table, dict):
        rows = table.get("rows")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        return [table]
    if isinstance(table, list):
        return [r for r in table if isinstance(r, dict)]
    return []


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip() or "待核验"
