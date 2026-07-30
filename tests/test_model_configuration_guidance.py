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
        self.assertEqual(comic["cabinet"], "text")
        self.assertEqual(comic["zhongshu"], "text")
        self.assertEqual(comic["menxia"], "text")
        self.assertEqual(comic["hubu"], "text")
        self.assertEqual(comic["bingbu"], "text")
        self.assertEqual(comic["gongbu"], "image_generation")
        self.assertEqual(comic["xingbu"], "vision_understanding")
        self.assertEqual(comic["libu"], "text")

        research = {
            item["department_id"]: item["required_capability"]
            for item in matrix["offices"]["research"]["departments"]
        }
        self.assertEqual(research["zhongshu"], "text")
        self.assertEqual(research["menxia"], "text")
        self.assertEqual(research["hubu"], "text")
        self.assertEqual(research["bingbu"], "text")
        self.assertEqual(research["gongbu"], "browser_or_human_evidence")


if __name__ == "__main__":
    unittest.main()
