import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.export_public_showcase import export_public_showcase
from scripts import verify_portfolio_showcase_sync as sync


class PortfolioShowcaseSyncTests(unittest.TestCase):
    def setUp(self):
        Path("dist").mkdir(exist_ok=True)
        self.source_dir = Path(tempfile.mkdtemp(prefix=".test-showcase-source-", dir="dist"))
        self.target_dir = Path(tempfile.mkdtemp(prefix=".test-showcase-target-", dir="dist"))
        export_public_showcase(self.source_dir)
        shutil.rmtree(self.target_dir)
        shutil.copytree(self.source_dir, self.target_dir)

    def tearDown(self):
        for path in (self.source_dir, self.target_dir):
            if path.exists():
                shutil.rmtree(path)

    def test_matching_copy_passes(self):
        payload = sync.verify_portfolio_showcase_sync(self.source_dir, self.target_dir)

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["missing_files"], [])
        self.assertEqual(payload["mismatched_files"], [])
        self.assertEqual(payload["compared_files"], payload["source_file_count"])

    def test_missing_or_stale_copy_fails_with_actionable_files(self):
        (self.target_dir / "app.js").write_text("stale app", encoding="utf-8")
        (self.target_dir / "style.css").unlink()

        payload = sync.verify_portfolio_showcase_sync(self.source_dir, self.target_dir)

        self.assertEqual(payload["status"], "failed")
        self.assertIn("app.js", payload["mismatched_files"])
        self.assertIn("style.css", payload["missing_files"])
        self.assertTrue(any("differ" in item for item in payload["errors"]))
        self.assertTrue(any("missing" in item for item in payload["errors"]))

    def test_explicit_missing_target_fails(self):
        missing_target = self.target_dir.parent / f"{self.target_dir.name}-missing"
        if missing_target.exists():
            shutil.rmtree(missing_target)

        payload = sync.verify_portfolio_showcase_sync(self.source_dir, missing_target)

        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("target showcase directory is missing" in item for item in payload["errors"]))

    def test_default_missing_personal_site_is_skipped(self):
        missing_site = self.target_dir.parent / f"{self.target_dir.name}-missing-site"
        if missing_site.exists():
            shutil.rmtree(missing_site)

        with mock.patch.object(sync, "DEFAULT_PERSONAL_SITE", missing_site):
            payload = sync.verify_portfolio_showcase_sync(self.source_dir)

        self.assertEqual(payload["status"], "skipped")
        self.assertIn("--target-dir", payload["next_action"])
        self.assertTrue(any("default personal website target is not present" in item for item in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
