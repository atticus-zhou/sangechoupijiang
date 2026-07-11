import importlib.util
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
        self.assertIn("office_models.comic_production.gongbu", text)
        self.assertIn("office_models.comic_production.xingbu", text)
        self.assertIn("不要提交真实 Key", text)


if __name__ == "__main__":
    unittest.main()
