import unittest


class ComicProductionReadinessTests(unittest.TestCase):
    def test_real_product_readiness_is_evidence_backed_without_demo_mode(self):
        from src.product_readiness import audit_comic_production_readiness

        audit = audit_comic_production_readiness()
        checks = {item["id"]: item for item in audit["checks"]}

        self.assertEqual(audit["office_id"], "comic_production")
        self.assertEqual(audit["mode"], "real_product_without_demo")
        self.assertEqual(audit["status"], "ready_without_demo")
        self.assertNotIn("no_key_demo", checks)

        for check_id in (
            "workflow_state",
            "downloadable_delivery",
            "model_preflight",
            "local_doctor",
            "end_to_end_verifier",
            "readme",
            "failure_handling",
        ):
            self.assertIn(check_id, checks)
            self.assertEqual(checks[check_id]["status"], "passed")
            self.assertTrue(checks[check_id]["evidence"])
        self.assertTrue(any("办公室可用性" in item for item in checks["local_doctor"]["evidence"]))
        self.assertTrue(any('"offices"' in item for item in checks["local_doctor"]["evidence"]))

    def test_real_product_readiness_can_be_rendered_for_tasklist(self):
        from src.product_readiness import audit_comic_production_readiness, format_readiness_markdown

        markdown = format_readiness_markdown(audit_comic_production_readiness())

        self.assertIn("AI 漫剧制片办公室真实产品 readiness", markdown)
        self.assertIn("完整工作流状态", markdown)
        self.assertIn("可下载交付物", markdown)
        self.assertIn("本地自检命令", markdown)
        self.assertIn("失败处理策略", markdown)


if __name__ == "__main__":
    unittest.main()
