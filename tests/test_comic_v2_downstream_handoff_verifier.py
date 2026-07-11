import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_comic_v2_downstream_handoff.py")
FIXTURE = Path("tests/fixtures/comic_v2_sample.json")
UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class ComicV2DownstreamHandoffVerifierTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.spec_from_file_location("verify_comic_v2_downstream_handoff", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_fixture_package_is_downstream_handoff_ready(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            result = module.verify_downstream_handoff(FIXTURE, Path(tmp))

        self.assertEqual(result["status"], "passed", result["errors"])
        self.assertTrue(result["downstream_handoff_ready"])
        self.assertEqual(result["asset_count"], 3)
        self.assertEqual(result["image_count"], 7)
        self.assertEqual(result["shot_count"], 2)
        self.assertEqual(result["character_identity_sets"], 1)
        self.assertEqual(result["prop_reference_sets"], 1)
        self.assertEqual(result["scene_spatial_sets"], 1)
        self.assertEqual(result["shot_video_packages"], 2)
        self.assertGreaterEqual(result["lineage_stage_count"], 7)

    def test_cli_json_exposes_downstream_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixture",
                    str(FIXTURE),
                    "--output-dir",
                    tmp,
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=UTF8_ENV,
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["downstream_handoff_ready"])
        self.assertIn("handoff_manifest", payload)
        self.assertEqual(payload["errors"], [])

    def test_cli_markdown_is_readable_for_reviewers(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixture",
                    str(FIXTURE),
                    "--output-dir",
                    tmp,
                    "--format",
                    "markdown",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=UTF8_ENV,
            )

        self.assertIn("Comic V2 Downstream Handoff Audit", completed.stdout)
        self.assertIn("Downstream Readiness", completed.stdout)
        self.assertIn("Character identity sets", completed.stdout)
        self.assertIn("Shot video packages", completed.stdout)


if __name__ == "__main__":
    unittest.main()
