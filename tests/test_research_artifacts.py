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
        self.assertIn("briefing", artifact_types)
        self.assertIn("chart_plan", artifact_types)
        self.assertIn("screenshot_plan", artifact_types)
        self.assertIn("source_list", artifact_types)
        self.assertIn("data_table", artifact_types)
        self.assertIn("competitor_table", artifact_types)
        self.assertIn("review_pain_points", artifact_types)
        self.assertIn("opportunity_map", artifact_types)
        self.assertTrue(all(a["artifact_id"].startswith("art_task1_") for a in artifacts))

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


if __name__ == "__main__":
    unittest.main()
