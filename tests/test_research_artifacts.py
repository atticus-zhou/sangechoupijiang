import unittest

from src.research_artifacts import build_research_artifacts


class ResearchArtifactTests(unittest.TestCase):
    def test_builds_research_package_from_completed_result(self):
        result = {
            "final_report": (
                "# 投影仪市场报告\n\n"
                "市场规模持续增长，头部品牌份额集中。\n\n"
                "价格段分布呈现高端化趋势。\n"
            ),
            "plan": {"title": "投影仪市场报告"},
            "results": [
                {
                    "step_id": 1,
                    "department": "兵部",
                    "status": "verified",
                    "summary": "完成市场规模与品牌份额整理",
                    "context_refs": ["https://example.com/source-a"],
                },
                {
                    "step_id": 2,
                    "department": "工部",
                    "status": "completed",
                    "summary": "完成报告",
                },
            ],
        }

        artifacts = build_research_artifacts("task1", result)
        artifact_types = {a["artifact_type"] for a in artifacts}

        self.assertIn("report", artifact_types)
        self.assertIn("standard_report", artifact_types)
        self.assertIn("briefing", artifact_types)
        self.assertIn("chart_plan", artifact_types)
        self.assertIn("screenshot_plan", artifact_types)
        self.assertIn("source_list", artifact_types)
        self.assertIn("data_table", artifact_types)
        self.assertIn("competitor_table", artifact_types)
        self.assertIn("review_pain_points", artifact_types)
        self.assertIn("opportunity_map", artifact_types)
        self.assertTrue(all(a["artifact_id"].startswith("art_task1_") for a in artifacts))

        by_type = {a["artifact_type"]: a for a in artifacts}
        standard_report = by_type["standard_report"]["content"]
        for heading in (
            "## 行业概览",
            "## 竞品对比",
            "## 价格带与数据要点",
            "## 用户痛点",
            "## 差异化机会",
            "## 风险与建议",
            "## 证据与待核验",
        ):
            self.assertIn(heading, standard_report)
        self.assertIn("来源清单", standard_report)

    def test_source_list_falls_back_when_sources_are_missing(self):
        result = {
            "final_report": "简短报告",
            "plan": {"title": "报告"},
            "results": [{"step_id": 1, "summary": "无来源"}],
        }

        artifacts = build_research_artifacts("task2", result)
        source = next(a for a in artifacts if a["artifact_type"] == "source_list")

        self.assertIn("暂未形成结构化来源清单", source["content"])

    def test_uses_structured_sources_data_points_and_chart_suggestions(self):
        result = {
            "final_report": "市场规模增长，品牌份额集中。",
            "plan": {"title": "结构化报告"},
            "results": [{
                "step_id": 1,
                "department": "兵部",
                "status": "verified",
                "summary": "完成资料整理",
                "sources": [{
                    "title": "行业报告",
                    "url": "https://example.com/report",
                    "publisher": "Example Research",
                    "published_at": "2026-01",
                    "note": "市场规模数据",
                }],
                "data_points": [{
                    "metric": "市场规模",
                    "value": "待核验",
                    "period": "2026",
                    "source_url": "https://example.com/report",
                    "confidence": "medium",
                    "note": "需二次核验",
                }],
                "chart_suggestions": [{
                    "title": "市场规模趋势",
                    "chart_type": "line",
                    "purpose": "展示增长趋势",
                    "data_needed": "年度市场规模",
                }],
                "competitors": [{
                    "product_name": "样例竞品",
                    "brand": "样例品牌",
                    "sales": "待核验",
                    "price": "99元",
                    "selling_points": "低价高转化",
                    "target_user": "入门用户",
                    "positive_keywords": "便宜",
                    "negative_pain_points": "质量不稳定",
                }],
            }],
        }

        artifacts = build_research_artifacts("task3", result)
        by_type = {a["artifact_type"]: a for a in artifacts}

        self.assertIn("Example Research", by_type["source_list"]["content"])
        self.assertIn("市场规模", by_type["data_table"]["content"])
        self.assertIn("line", by_type["chart_plan"]["content"])
        self.assertIn("evidence_01.png", by_type["screenshot_plan"]["content"])
        self.assertIn("样例竞品", by_type["competitor_table"]["content"])
        self.assertIn("样例竞品", by_type["standard_report"]["content"])
        self.assertIn("https://example.com/report", by_type["standard_report"]["content"])

    def test_research_artifacts_record_schema_gate_audits(self):
        result = {
            "final_report": "Market size grows steadily. Source: https://example.com/report",
            "plan": {"title": "Schema checked report"},
            "results": [{
                "step_id": 1,
                "department": "bingbu",
                "status": "verified",
                "summary": "Collected source, market metric, and competitor evidence.",
                "sources": [{
                    "title": "Industry report",
                    "url": "https://example.com/report",
                    "publisher": "Example Research",
                    "published_at": "2026-01",
                    "note": "Market size evidence",
                }],
                "data_points": [{
                    "metric": "Market size",
                    "value": "12 billion",
                    "period": "2026",
                    "source_url": "https://example.com/report",
                    "confidence": "high",
                    "note": "Verified sample",
                }],
                "competitors": [{
                    "product_name": "Sample product",
                    "brand": "Sample brand",
                    "sales": "10000",
                    "price": "99",
                    "selling_points": "Fast delivery",
                    "target_user": "Entry users",
                    "positive_keywords": "cheap",
                    "negative_pain_points": "quality varies",
                }],
            }],
        }

        artifacts = build_research_artifacts("task_schema", result)
        by_type = {a["artifact_type"]: a for a in artifacts}

        expected_gates = {
            "standard_report": "research_standard_report",
            "source_list": "research_source_list",
            "data_table": "research_data_table",
            "competitor_table": "research_competitor_table",
        }
        for artifact_type, schema_id in expected_gates.items():
            schema_gate = by_type[artifact_type]["metadata"]["schema_gate"]
            self.assertEqual(schema_gate["schema_id"], schema_id)
            self.assertEqual(schema_gate["status"], "passed")

        self.assertNotIn("quality_report", by_type)

    def test_research_artifacts_create_quality_report_when_schema_gate_fails(self):
        result = {
            "final_report": "Short report without traceable evidence.",
            "plan": {"title": "Weak report"},
            "results": [{
                "step_id": 1,
                "department": "bingbu",
                "status": "completed",
                "summary": "No sources yet.",
            }],
        }

        artifacts = build_research_artifacts("task_bad_schema", result)
        by_type = {a["artifact_type"]: a for a in artifacts}

        self.assertIn("quality_report", by_type)
        quality_report = by_type["quality_report"]
        self.assertIn("质量报告", quality_report["content"])
        self.assertIn("交付物", quality_report["content"])
        self.assertIn("research_source_list", quality_report["content"])
        self.assertIn("schema_gate", quality_report["metadata"])
        self.assertEqual(quality_report["metadata"]["schema_gate"]["status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
