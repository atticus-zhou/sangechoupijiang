import json
import subprocess
import sys
import unittest


class ComicV2ProductionBenchmarkVerifierTests(unittest.TestCase):
    def test_json_reports_honest_fixture_quality_claim(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_v2_production_benchmark.py",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["quality_claim"], "demo_structure_verified")
        self.assertEqual(payload["package_quality_score"], 100)
        self.assertTrue(payload["package_quality_ready"])
        self.assertFalse(payload["production_quality_verified"])
        self.assertEqual(payload["visual_evidence_level"], "fixture_only")
        self.assertEqual(payload["image_quality_summary"]["total_images"], 7)
        self.assertEqual(payload["image_quality_summary"]["usable_images"], 7)
        self.assertEqual(payload["image_quality_summary"]["waste_or_rework_images"], 0)
        self.assertTrue(payload["stored_benchmark_matches"])
        self.assertEqual(payload["manifest_schema_version"], 3)

    def test_markdown_is_readable_and_discloses_fixture_limit(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_v2_production_benchmark.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("AI Comic Production Quality Benchmark", completed.stdout)
        self.assertIn("Package quality score: `100/100`", completed.stdout)
        self.assertIn("Quality claim: `demo_structure_verified`", completed.stdout)
        self.assertIn("Visual evidence: `fixture_only`", completed.stdout)
        self.assertIn("Image Quality Summary", completed.stdout)
        self.assertIn("Total images: `7`", completed.stdout)
        self.assertIn("Waste/rework images: `0`", completed.stdout)
        self.assertIn("不证明真实模型", completed.stdout)


if __name__ == "__main__":
    unittest.main()
