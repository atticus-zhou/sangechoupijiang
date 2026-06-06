import unittest

from src.research_office import (
    build_evidence_fallback_result,
    format_workspace_evidence_context,
    needs_platform_evidence,
    research_capture_keyword,
)


class ResearchOfficeWorkflowTests(unittest.TestCase):
    def test_extracts_research_keyword(self):
        self.assertEqual(research_capture_keyword("研究对象：民用无人机\n需要截图"), "民用无人机")
        self.assertEqual(research_capture_keyword("开品调研：吹风机，重点看飞瓜"), "吹风机")

    def test_platform_evidence_only_for_research_office(self):
        self.assertTrue(needs_platform_evidence("调研吹风机，需要飞瓜截图", "research"))
        self.assertFalse(needs_platform_evidence("调研吹风机，需要飞瓜截图", "technical"))

    def test_formats_evidence_context(self):
        context = format_workspace_evidence_context([
            {
                "artifact_type": "screenshot_extraction",
                "title": "飞瓜商品详情",
                "uri": "/files/shot.png",
                "content": "近30天销量：5w-10w",
            },
            {"artifact_type": "unrelated", "title": "ignore", "content": "ignore"},
        ])

        self.assertIn("飞瓜商品详情", context)
        self.assertIn("近30天销量", context)
        self.assertNotIn("ignore", context)

    def test_builds_evidence_fallback_report(self):
        result = build_evidence_fallback_result(
            task_id="task-1",
            workspace_id="ws-1",
            user_request="研究对象：吹风机",
            reason="timeout",
            artifacts=[
                {"artifact_type": "screenshot_evidence", "title": "截图", "content": "已入库"},
                {"artifact_type": "screenshot_extraction", "title": "识别", "content": "销量：5w-10w"},
            ],
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["metadata"]["fallback"])
        self.assertEqual(result["metadata"]["screenshot_count"], 1)
        self.assertIn("吹风机研究报告", result["final_report"])
        self.assertIn("销量：5w-10w", result["final_report"])


if __name__ == "__main__":
    unittest.main()
