import unittest

from src.research_office.output_schemas import (
    ResearchOutputSchemaError,
    list_research_output_schemas,
    validate_research_output_schema,
)


class ResearchOutputSchemaTests(unittest.TestCase):
    def test_research_schema_registry_declares_core_delivery_gates(self):
        schemas = {item["schema_id"]: item for item in list_research_output_schemas()}

        self.assertIn("research_standard_report", schemas)
        self.assertIn("research_source_list", schemas)
        self.assertIn("research_data_table", schemas)
        self.assertIn("research_competitor_table", schemas)
        self.assertEqual(schemas["research_standard_report"]["office_id"], "research")
        self.assertEqual(schemas["research_source_list"]["owner_agent"], "bingbu")
        self.assertEqual(schemas["research_data_table"]["owner_agent"], "hubu")

    def test_standard_report_requires_boss_ready_sections_and_evidence(self):
        content = "\n".join([
            "# 民用无人机 - 标准调研报告",
            "## 行业概览",
            "低空经济政策带动民用无人机需求。",
            "## 竞品对比",
            "| 产品名称 | 品牌 |",
            "| --- | --- |",
            "| Mini 4 Pro | DJI |",
            "## 价格带与数据要点",
            "| 指标 | 数值 |",
            "| --- | --- |",
            "| 主流价格带 | 3000-6000元 |",
            "## 用户痛点",
            "| 问题类型 | 典型差评原文 |",
            "| 续航 | 电池不够用 |",
            "## 差异化机会",
            "| 机会点 | 机会分析 |",
            "| --- | --- |",
            "| 长续航 | 适合户外拍摄 |",
            "## 风险与建议",
            "- 监管合规需要复核。",
            "## 证据与待核验",
            "来源清单：",
            "| 来源 | URL |",
            "| 行业报告 | https://example.com/report |",
        ])

        result = validate_research_output_schema("research_standard_report", {"content": content})

        self.assertEqual(result["schema_id"], "research_standard_report")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["section_count"], 7)

    def test_standard_report_rejects_plain_ai_text(self):
        with self.assertRaises(ResearchOutputSchemaError) as ctx:
            validate_research_output_schema(
                "research_standard_report",
                {"content": "这个市场很好，建议进入。"},
            )

        self.assertIn("missing required sections", str(ctx.exception))

    def test_source_data_and_competitor_tables_require_markdown_tables(self):
        self.assertEqual(
            validate_research_output_schema(
                "research_source_list",
                {"content": "| 来源 | URL |\n| --- | --- |\n| A | https://example.com |"},
            )["status"],
            "passed",
        )
        self.assertEqual(
            validate_research_output_schema(
                "research_data_table",
                {"content": "| 指标 | 数值 | 来源 |\n| --- | --- | --- |\n| 市场规模 | 待核验 | https://example.com |"},
            )["status"],
            "passed",
        )
        self.assertEqual(
            validate_research_output_schema(
                "research_competitor_table",
                {"content": "| 产品名称 | 品牌 | 价格 |\n| --- | --- | --- |\n| A | B | 99元 |"},
            )["status"],
            "passed",
        )

        with self.assertRaises(ResearchOutputSchemaError):
            validate_research_output_schema("research_source_list", {"content": "暂无来源"})


if __name__ == "__main__":
    unittest.main()
