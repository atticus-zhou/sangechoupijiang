import unittest


class ComicProductionReadinessTests(unittest.TestCase):
    def test_real_product_readiness_is_evidence_backed_with_no_key_demo_mode(self):
        from src.product_readiness import audit_comic_production_readiness

        audit = audit_comic_production_readiness()
        checks = {item["id"]: item for item in audit["checks"]}

        self.assertEqual(audit["office_id"], "comic_production")
        self.assertEqual(audit["mode"], "real_product_with_no_key_demo")
        self.assertEqual(audit["status"], "ready_with_demo")
        self.assertIn("no_key_demo", checks)

        for check_id in (
            "workflow_state",
            "downloadable_delivery",
            "model_preflight",
            "local_doctor",
            "end_to_end_verifier",
            "history_trace",
            "no_key_demo",
            "runtime_status",
            "long_task_observability",
            "readme",
            "failure_handling",
        ):
            self.assertIn(check_id, checks)
            self.assertEqual(checks[check_id]["status"], "passed")
            self.assertTrue(checks[check_id]["evidence"])
        self.assertTrue(any("办公室可用性" in item for item in checks["local_doctor"]["evidence"]))
        self.assertTrue(any('"offices"' in item for item in checks["local_doctor"]["evidence"]))
        runtime_evidence = "\n".join(checks["runtime_status"]["evidence"])
        self.assertIn("src/web/static/js/app.js", runtime_evidence)
        self.assertIn("src/web/static/index.html", runtime_evidence)
        self.assertIn("src/web/static/css/style.css", runtime_evidence)
        long_task_evidence = "\n".join(checks["long_task_observability"]["evidence"])
        self.assertIn("src/web/app.py", long_task_evidence)
        self.assertIn("scripts/verify_comic_v2_user_flow.py", long_task_evidence)
        self.assertIn("tests/test_comic_v2_pipeline.py", long_task_evidence)
        schema_evidence = "\n".join(checks["agent_output_schema_gate"]["evidence"])
        self.assertIn("src/offices.py", schema_evidence)
        self.assertIn("src/research_office/output_schemas.py", schema_evidence)
        self.assertIn("src/research_artifacts.py", schema_evidence)
        self.assertIn("src/web/static/js/app.js", schema_evidence)
        self.assertIn("src/web/static/css/style.css", schema_evidence)
        self.assertIn("tests/test_research_output_schemas.py", schema_evidence)
        self.assertIn("tests/test_research_artifacts.py", schema_evidence)
        demo_evidence = "\n".join(checks["no_key_demo"]["evidence"])
        self.assertIn("quality_gates", demo_evidence)
        self.assertIn("demo-quality-gates", demo_evidence)
        self.assertIn("evidence_links", demo_evidence)
        self.assertIn("/api/demo/comic-production/files/word_canvas.docx", demo_evidence)
        self.assertIn("/api/demo/research/files/report.md", demo_evidence)
        self.assertIn("scripts/verify_public_demo_mode.py", demo_evidence)

    def test_real_product_readiness_can_be_rendered_for_tasklist(self):
        from src.product_readiness import audit_comic_production_readiness, format_readiness_markdown

        markdown = format_readiness_markdown(audit_comic_production_readiness())
        self.assertIn("历史追溯", markdown)

        self.assertIn("AI 漫剧制片办公室真实产品 readiness", markdown)
        self.assertIn("完整工作流状态", markdown)
        self.assertIn("可下载交付物", markdown)
        self.assertIn("本地自检命令", markdown)
        self.assertIn("失败处理策略", markdown)


if __name__ == "__main__":
    unittest.main()
