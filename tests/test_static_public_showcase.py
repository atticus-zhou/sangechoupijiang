import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.export_public_showcase import export_public_showcase


class StaticPublicShowcaseTests(unittest.TestCase):
    def setUp(self):
        Path("dist").mkdir(exist_ok=True)
        self.output_dir = Path(tempfile.mkdtemp(prefix=".test-public-showcase-", dir="dist"))

    def tearDown(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    def test_export_is_backend_free_and_contains_real_downloads(self):
        summary = export_public_showcase(self.output_dir)

        self.assertEqual(summary["status"], "passed")
        self.assertFalse(summary["requires_backend"])
        self.assertFalse(summary["requires_api_key"])
        self.assertFalse(summary["calls_real_models"])
        self.assertEqual(summary["download_count"], 5)

        manifest = json.loads((self.output_dir / "export-manifest.json").read_text(encoding="utf-8"))
        showcase = json.loads((self.output_dir / "showcase.json").read_text(encoding="utf-8"))
        index_text = (self.output_dir / "index.html").read_text(encoding="utf-8")
        self.assertEqual(showcase["mode"], "public_no_key_static_showcase")
        self.assertIn('<link rel="icon" href="data:,">', index_text)
        self.assertFalse(showcase["static_export"]["requires_backend"])
        demos = {item["office_id"]: item for item in showcase["featured_demos"]}
        comic_benchmark = demos["comic_production"]["quality_benchmark"]
        self.assertEqual(comic_benchmark["status"], "demo_structure_verified")
        self.assertFalse(comic_benchmark["production_quality_verified"])
        claim = showcase["portfolio_embed"]["real_production_claim"]
        self.assertEqual(claim["uri"], "data/comic_production_claim_report.json")
        self.assertEqual(claim["claim_level"], "demo_structure_only")
        self.assertFalse(claim["can_claim_real_quality"])
        self.assertNotIn("E:\\", json.dumps(claim, ensure_ascii=False))
        claim_payload = json.loads((self.output_dir / claim["uri"]).read_text(encoding="utf-8"))
        self.assertEqual(claim_payload["claim_level"], "demo_structure_only")
        self.assertFalse(claim_payload["can_claim_real_quality"])
        self.assertFalse(claim_payload["calls_real_models"])
        self.assertFalse(claim_payload["requires_api_key"])
        self.assertNotIn("E:\\", json.dumps(claim_payload, ensure_ascii=False))
        script_text = "\n".join(
            item["product_response"] for item in showcase["portfolio_embed"]["interview_demo_script"]
        )
        self.assertIn("访客打开页面时只读取随包的 data.js", script_text)
        self.assertIn("已经随静态站点一起导出", script_text)
        self.assertIn("页面运行时不连接 FastAPI", "\n".join(showcase["safety_boundaries"]))
        self.assertGreater((self.output_dir / "assets" / "public-showcase-desktop.png").stat().st_size, 100_000)
        for item in manifest["downloads"]:
            self.assertFalse(item["local_uri"].startswith("/"))
            self.assertGreater((self.output_dir / item["local_uri"]).stat().st_size, 20)
        for item in showcase["portfolio_embed"]["deliverable_reading_guide"]:
            self.assertTrue((self.output_dir / item["uri"]).is_file())
        static_script = (self.output_dir / "app.js").read_text(encoding="utf-8")
        self.assertIn("未宣称真实画质", static_script)
        self.assertIn("handoff_inventory", json.dumps(showcase["portfolio_embed"], ensure_ascii=False))

    def test_static_readiness_verifier_is_public_operator_readable(self):
        completed = subprocess.run(
            [sys.executable, "scripts/verify_static_public_showcase.py", "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Static Public Showcase Readiness", completed.stdout)
        self.assertIn("Status: `passed`", completed.stdout)
        self.assertIn("Downloadable deliverables: 5", completed.stdout)
        self.assertIn("Reading guide: 5/5", completed.stdout)
        self.assertIn("Comic claim report: data/comic_production_claim_report.json / ready=True", completed.stdout)
        self.assertIn("Requires backend: False", completed.stdout)


if __name__ == "__main__":
    unittest.main()
