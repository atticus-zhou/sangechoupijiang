import unittest

from src.research_quality import assess_research_package


class ResearchQualityTests(unittest.TestCase):
    def test_ready_package_scores_high(self):
        artifacts = [
            {"artifact_type": "report", "content": "完整报告" * 500},
            {"artifact_type": "standard_report", "content": "\n".join([
                "## 行业概览",
                "## 竞品对比",
                "## 价格带与数据要点",
                "## 用户痛点",
                "## 差异化机会",
                "## 风险与建议",
                "## 证据与待核验",
                "来源清单：有",
            ])},
            {"artifact_type": "briefing", "content": "摘要"},
            {"artifact_type": "source_list", "content": "| 来源 | URL |\n| A | https://example.com |"},
            {"artifact_type": "data_table", "content": "| 指标 | 数值 |"},
            {"artifact_type": "competitor_table", "content": "| 产品名称 | 品牌 |"},
            {"artifact_type": "review_pain_points", "content": "| 问题类型 |"},
            {"artifact_type": "opportunity_map", "content": "| 机会点 |"},
            {"artifact_type": "chart_plan", "content": "| 图表 | 用途 |"},
            {"artifact_type": "screenshot_plan", "content": "| 截图对象 | URL |"},
        ]

        quality = assess_research_package(artifacts)

        self.assertEqual(quality["status"], "ready")
        self.assertFalse(quality["missing_artifacts"])

    def test_missing_sources_needs_review(self):
        artifacts = [
            {"artifact_type": "report", "content": "市场规模 X百万台，TODO" * 20},
            {"artifact_type": "source_list", "content": "暂未形成结构化来源清单。"},
        ]

        quality = assess_research_package(artifacts)

        self.assertIn("briefing", quality["missing_artifacts"])
        self.assertTrue(quality["warnings"])
        self.assertNotEqual(quality["status"], "ready")

    def test_missing_standard_report_structure_needs_review(self):
        artifacts = [
            {"artifact_type": "report", "content": "完整报告" * 500},
            {"artifact_type": "standard_report", "content": "只有普通正文，没有标准章节。"},
            {"artifact_type": "briefing", "content": "摘要"},
            {"artifact_type": "source_list", "content": "| 来源 | URL |\n| A | https://example.com |"},
            {"artifact_type": "data_table", "content": "| 指标 | 数值 |"},
            {"artifact_type": "competitor_table", "content": "| 产品名称 | 品牌 |"},
            {"artifact_type": "review_pain_points", "content": "| 问题类型 |"},
            {"artifact_type": "opportunity_map", "content": "| 机会点 |"},
            {"artifact_type": "chart_plan", "content": "| 图表 | 用途 |"},
            {"artifact_type": "screenshot_plan", "content": "| 截图对象 | URL |"},
        ]

        quality = assess_research_package(artifacts)

        self.assertNotEqual(quality["status"], "ready")
        self.assertTrue(any("标准报告" in warning for warning in quality["warnings"]))


if __name__ == "__main__":
    unittest.main()
