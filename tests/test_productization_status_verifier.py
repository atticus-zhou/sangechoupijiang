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
        self.assertEqual(len(payload["requirements"]), 8)
        self.assertTrue(payload["release_gate_includes_status"])
        self.assertTrue(payload["readme_links_status"])

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


if __name__ == "__main__":
    unittest.main()
