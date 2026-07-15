from pathlib import Path
import unittest


class PublicReleaseHandoffDocTests(unittest.TestCase):
    def test_public_release_handoff_doc_exists_and_sets_boundaries(self):
        text = Path("docs/PUBLIC_RELEASE_HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("/api/demo/public-showcase", text)
        self.assertIn("dist/public-showcase", text)
        self.assertIn("handoff manifest", text)
        self.assertIn("AI 漫剧 Word 制片画布", text)
        self.assertIn("待补证据交接表", text)
        self.assertIn("API Key", text)
        self.assertIn("SaaS", text)
        self.assertIn("FastAPI", text)

    def test_public_release_handoff_doc_lists_required_release_gates(self):
        text = Path("docs/PUBLIC_RELEASE_HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/verify_productization_status.py --format markdown", text)
        self.assertIn("python scripts/verify_first_run_readiness.py --format markdown", text)
        self.assertIn("python scripts/verify_public_demo_mode.py --format markdown", text)
        self.assertIn("python scripts/export_public_showcase.py", text)
        self.assertIn("python scripts/verify_static_public_showcase.py --format markdown", text)
        self.assertIn("python scripts/verify_comic_v2_delivery.py --format markdown", text)
        self.assertIn("python scripts/verify_comic_v2_downstream_handoff.py --format markdown", text)
        self.assertIn("python scripts/verify_research_office_readiness.py --format markdown", text)
        self.assertIn("python scripts/verify_release_readiness.py --format markdown", text)
        self.assertIn("python scripts/check_no_secrets.py", text)

    def test_readme_links_public_release_handoff_doc(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("docs/PUBLIC_RELEASE_HANDOFF.md", text)
        self.assertIn("公开演示和部署边界", text)
        self.assertIn("不要把自己的 API Key 暴露给访问者", text)


if __name__ == "__main__":
    unittest.main()
