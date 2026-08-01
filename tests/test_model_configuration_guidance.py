import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_model_configuration_guidance.py")


class ModelConfigurationGuidanceTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.spec_from_file_location("verify_model_configuration_guidance", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_model_configuration_guidance_passes(self):
        module = self._module()
        payload = module.verify_model_configuration_guidance()
        self.assertEqual(payload["status"], "passed", payload.get("failures"))
        self.assertFalse(payload["failures"])
        self.assertGreaterEqual(len(payload["checks"]), 7)

    def test_markdown_output_is_human_readable(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Model Configuration Guidance Audit", completed.stdout)
        self.assertIn("Model configuration guide exists", completed.stdout)
        self.assertIn("config.example.yaml", completed.stdout)
        self.assertIn("Office Model Setup Summary", completed.stdout)
        self.assertIn("AI Comic Setup Ladder", completed.stdout)
        self.assertIn("minimum_text", completed.stdout)
        self.assertIn("full_comic_production", completed.stdout)
        self.assertIn("browser_or_human_evidence", completed.stdout)

    def test_payload_explains_office_model_setup_summary(self):
        module = self._module()
        payload = module.verify_model_configuration_guidance()

        summaries = {
            item["office_id"]: item
            for item in payload["office_model_setup_summary"]
        }
        self.assertIn("comic_production", summaries)
        self.assertIn("research", summaries)

        comic = summaries["comic_production"]
        self.assertGreaterEqual(comic["capability_counts"]["text"], 6)
        self.assertEqual(comic["capability_counts"]["image_generation"], 1)
        self.assertEqual(comic["capability_counts"]["vision_understanding"], 1)
        self.assertTrue(comic["requires_image_generation"])
        self.assertTrue(comic["requires_vision_understanding"])

        research = summaries["research"]
        self.assertEqual(research["capability_counts"]["browser_or_human_evidence"], 1)
        self.assertEqual(research["capability_counts"]["vision_understanding"], 1)
        self.assertTrue(research["requires_browser_or_human_evidence"])

    def test_comic_setup_ladder_distinguishes_minimum_and_full_production(self):
        module = self._module()
        payload = module.verify_model_configuration_guidance()

        ladder = {item["level"]: item for item in payload["comic_setup_ladder"]}
        self.assertEqual(
            list(ladder),
            ["no_key_demo", "minimum_text", "full_comic_production"],
        )
        self.assertFalse(ladder["no_key_demo"]["requires_api_key"])
        self.assertTrue(ladder["minimum_text"]["requires_api_key"])
        self.assertIn("zhongshu", ladder["minimum_text"]["required_departments"])
        self.assertIn("bingbu", ladder["minimum_text"]["required_departments"])
        self.assertNotIn("gongbu", ladder["minimum_text"]["required_departments"])
        self.assertNotIn("xingbu", ladder["minimum_text"]["required_departments"])
        self.assertIn("gongbu", ladder["full_comic_production"]["required_departments"])
        self.assertIn("xingbu", ladder["full_comic_production"]["required_departments"])

    def test_guide_distinguishes_minimum_and_full_comic_setup(self):
        text = Path("docs/MODEL_CONFIGURATION.md").read_text(encoding="utf-8")

        self.assertIn("最小可跑配置", text)
        self.assertIn("完整制片配置", text)
        self.assertIn("工部", text)
        self.assertIn("刑部", text)
        self.assertIn("office_models.comic_production.bingbu", text)
        self.assertIn("office_models.comic_production.gongbu", text)
        self.assertIn("office_models.comic_production.xingbu", text)
        self.assertIn("常见误填", text)
        self.assertIn("把豆包 Seedream 填到兵部", text)
        self.assertIn("当前优先作为生图槽位使用", text)
        self.assertIn("文本规划交给中书省、兵部等文本部门", text)
        self.assertIn("不需要在工部同一槽位再填一个文本模型", text)
        self.assertIn("不要提交真实 Key", text)
        self.assertIn("docs/MODEL_CAPABILITY_MATRIX.json", text)

    def test_machine_readable_matrix_matches_department_roles(self):
        matrix = json.loads(Path("docs/MODEL_CAPABILITY_MATRIX.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["schema"], "three_cobblers_model_capability_matrix_v1")
        self.assertIn("API keys", matrix["safe_key_rule"])

        comic = {
            item["department_id"]: item["required_capability"]
            for item in matrix["offices"]["comic_production"]["departments"]
        }
        self.assertEqual(comic["zhongshu"], "text")
        self.assertEqual(comic["menxia"], "text")
        self.assertEqual(comic["shangshu"], "text")
        self.assertEqual(comic["libu"], "text")
        self.assertEqual(comic["hubu"], "text")
        self.assertEqual(comic["bingbu"], "text")
        self.assertEqual(comic["gongbu"], "image_generation")
        self.assertEqual(comic["xingbu"], "vision_understanding")
        self.assertEqual(comic["libu_comm"], "text")

        research = {
            item["department_id"]: item["required_capability"]
            for item in matrix["offices"]["research"]["departments"]
        }
        self.assertEqual(research["zhongshu"], "text")
        self.assertEqual(research["menxia"], "text")
        self.assertEqual(research["shangshu"], "text")
        self.assertEqual(research["libu"], "text")
        self.assertEqual(research["hubu"], "text")
        self.assertEqual(research["bingbu"], "text")
        self.assertEqual(research["xingbu"], "vision_understanding")
        self.assertEqual(research["gongbu"], "browser_or_human_evidence")


if __name__ == "__main__":
    unittest.main()
