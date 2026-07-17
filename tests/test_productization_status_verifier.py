import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_productization_status.py")


class ProductizationStatusVerifierTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.spec_from_file_location("verify_productization_status", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_productization_status_passes(self):
        module = self._module()
        payload = module.verify_productization_status()
        self.assertEqual(payload["status"], "passed", payload.get("errors"))
        self.assertEqual(len(payload["requirements"]), 10)
        self.assertTrue(payload["release_gate_includes_status"])
        self.assertTrue(payload["readme_links_status"])
        office_governance = next(item for item in module.REQUIREMENTS if item["id"] == "P7")
        self.assertIn("required_demo_contract", office_governance["markers"])
        self.assertIn("starter checklist", office_governance["markers"])
        self.assertIn("docs/NEW_OFFICE_STARTER_CHECKLIST.md", office_governance["markers"])
        self.assertIn("short_video_ads", office_governance["markers"])
        self.assertIn("ecommerce_selection", office_governance["markers"])
        self.assertIn("story_ip", office_governance["markers"])
        self.assertIn("technical_project", office_governance["markers"])
        self.assertIn("future_schema_validators", office_governance["markers"])
        self.assertIn("future_recovery_events", office_governance["markers"])
        self.assertIn("docs/NEW_OFFICE_STARTER_CHECKLIST.md", office_governance["files"])
        self.assertIn("参观路径、证明点、下载物、阅读指南、面试脚本和公开安全边界", office_governance["markers"])
        comic_quality = next(item for item in module.REQUIREMENTS if item["id"] == "P10")
        self.assertIn("python scripts/verify_comic_v2_production_benchmark.py --format markdown", comic_quality["markers"])
        self.assertIn("tests/test_comic_v2_production_benchmark_verifier.py", comic_quality["files"])
        comic_recovery = next(item for item in module.REQUIREMENTS if item["id"] == "P5")
        self.assertIn("部门级恢复路由", comic_recovery["markers"])
        self.assertIn("旧版不可审计标记", comic_recovery["markers"])

    def test_markdown_output_is_readable(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("# Productization Status Audit", result.stdout)
        self.assertIn("Public portfolio demo boundary", result.stdout)
        self.assertIn("AI comic production handoff", result.stdout)
        self.assertIn("Model configuration guidance", result.stdout)
        self.assertIn("Downstream comic handoff readiness", result.stdout)
        self.assertIn("docs/NEW_OFFICE_STARTER_CHECKLIST.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
