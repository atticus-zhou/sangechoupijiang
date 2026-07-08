"""Schema gates for research-office delivery outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class ResearchOutputSchemaError(ValueError):
    """Raised when a research-office output misses required delivery structure."""


@dataclass(frozen=True)
class ResearchOutputSchema:
    office_id: str
    schema_id: str
    owner_agent: str
    stage: str
    description: str
    required_fields: tuple[str, ...]
    failure_impact: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_fields"] = list(self.required_fields)
        return payload


RESEARCH_STANDARD_SECTIONS = (
    "## 行业概览",
    "## 竞品对比",
    "## 价格带与数据要点",
    "## 用户痛点",
    "## 差异化机会",
    "## 风险与建议",
    "## 证据与待核验",
)


_SCHEMAS: dict[str, ResearchOutputSchema] = {
    "research_standard_report": ResearchOutputSchema(
        office_id="research",
        schema_id="research_standard_report",
        owner_agent="gongbu",
        stage="artifact_packaging",
        description="Boss-ready research report with required decision sections and evidence area.",
        required_fields=("content",),
        failure_impact="The research office would deliver generic AI text instead of a workplace-ready report.",
    ),
    "research_source_list": ResearchOutputSchema(
        office_id="research",
        schema_id="research_source_list",
        owner_agent="bingbu",
        stage="evidence_extraction",
        description="Traceable source table for URLs, publishers, dates, and notes.",
        required_fields=("content",),
        failure_impact="Report conclusions cannot be traced back to sources or pending evidence.",
    ),
    "research_data_table": ResearchOutputSchema(
        office_id="research",
        schema_id="research_data_table",
        owner_agent="hubu",
        stage="artifact_packaging",
        description="Structured data table for metrics, values, periods, confidence, and sources.",
        required_fields=("content",),
        failure_impact="The user cannot reuse market data in a report, slide, or boss briefing.",
    ),
    "research_competitor_table": ResearchOutputSchema(
        office_id="research",
        schema_id="research_competitor_table",
        owner_agent="hubu",
        stage="artifact_packaging",
        description="Structured competitor table for products, brands, pricing, selling points, and pain points.",
        required_fields=("content",),
        failure_impact="The research package cannot support competitive comparison or launch decisions.",
    ),
}


def list_research_output_schemas() -> list[dict[str, Any]]:
    return [schema.to_dict() for schema in _SCHEMAS.values()]


def validate_research_output_schema(schema_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    schema = _SCHEMAS.get(str(schema_id or "").strip())
    if schema is None:
        raise ResearchOutputSchemaError(f"unknown research output schema: {schema_id}")
    if not isinstance(payload, dict):
        raise ResearchOutputSchemaError(f"{schema.schema_id} output must be an object")
    missing = [field for field in schema.required_fields if not _has_value(payload.get(field))]
    if missing:
        raise ResearchOutputSchemaError(f"{schema.schema_id} missing fields: {', '.join(missing)}")
    content = str(payload.get("content") or "")
    if schema.schema_id == "research_standard_report":
        return _validate_standard_report(schema, content)
    if schema.schema_id == "research_source_list":
        return _validate_table(schema, content, required_headers=("来源", "URL"))
    if schema.schema_id == "research_data_table":
        return _validate_table(schema, content, required_headers=("指标", "数值"))
    if schema.schema_id == "research_competitor_table":
        return _validate_table(schema, content, required_headers=("产品名称", "品牌"))
    raise ResearchOutputSchemaError(f"no validator for schema: {schema.schema_id}")


def _validate_standard_report(schema: ResearchOutputSchema, content: str) -> dict[str, Any]:
    missing_sections = [section for section in RESEARCH_STANDARD_SECTIONS if section not in content]
    if missing_sections:
        raise ResearchOutputSchemaError(
            f"{schema.schema_id} missing required sections: {', '.join(missing_sections)}"
        )
    if "来源清单" not in content and "https://" not in content and "http://" not in content:
        raise ResearchOutputSchemaError(f"{schema.schema_id} missing evidence or source area")
    if _looks_like_placeholder_only(content):
        raise ResearchOutputSchemaError(f"{schema.schema_id} is mostly placeholders and needs evidence")
    return {
        "office_id": schema.office_id,
        "schema_id": schema.schema_id,
        "status": "passed",
        "section_count": len(RESEARCH_STANDARD_SECTIONS),
    }


def _validate_table(
    schema: ResearchOutputSchema,
    content: str,
    *,
    required_headers: tuple[str, ...],
) -> dict[str, Any]:
    if "|" not in content or "---" not in content:
        raise ResearchOutputSchemaError(f"{schema.schema_id} must be a markdown table")
    header = next((line for line in content.splitlines() if "|" in line), "")
    missing_headers = [header_name for header_name in required_headers if header_name not in header]
    if missing_headers:
        raise ResearchOutputSchemaError(
            f"{schema.schema_id} missing table headers: {', '.join(missing_headers)}"
        )
    data_rows = [
        line for line in content.splitlines()
        if line.strip().startswith("|") and "---" not in line and line != header
    ]
    if not data_rows:
        raise ResearchOutputSchemaError(f"{schema.schema_id} has no data rows")
    if _looks_like_placeholder_only("\n".join(data_rows)):
        raise ResearchOutputSchemaError(f"{schema.schema_id} only contains placeholders")
    return {
        "office_id": schema.office_id,
        "schema_id": schema.schema_id,
        "status": "passed",
        "row_count": len(data_rows),
    }


def _looks_like_placeholder_only(content: str) -> bool:
    compact = content.replace("|", "").replace("-", "").strip()
    if not compact:
        return True
    placeholders = ("待补充", "待核验", "暂无", "TODO")
    hits = sum(compact.count(item) for item in placeholders)
    return hits >= 3 and not ("http://" in compact or "https://" in compact)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True
