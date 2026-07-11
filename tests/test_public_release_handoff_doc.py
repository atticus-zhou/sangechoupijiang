from pathlib import Path
import unittest


class PublicReleaseHandoffDocTests(unittest.TestCase):
    def test_public_release_handoff_doc_exists_and_sets_boundaries(self):
        text = Path("docs/PUBLIC_RELEASE_HANDOFF.md").read_text(encoding="utf-8")

        self.assertNotIn("锟", text)
        self.assertNotIn("�", text)
        self.assertIn("公开发布交接说明", text)
        self.assertIn("/api/demo/public-showcase", text)
        self.assertIn("不宣称全自动飞瓜会员级调研", text)
        self.assertIn("不宣称当前版本已经是多用户 SaaS", text)
        self.assertIn("不要公开 API Key", text)
        self.assertIn("不宣称 AI 漫剧制片办公室会直接生成成片", text)
        self.assertIn("面试官或访客建议路径", text)
        self.assertIn("样例交付物阅读检查", text)
        self.assertIn("AI 漫剧 Word 制片画布", text)
        self.assertIn("handoff manifest", text)
        self.assertIn("研究办公室证据清单", text)
        self.assertIn("新开发者本地复现路径", text)

    def test_public_release_handoff_doc_lists_required_release_gates(self):
        text = Path("docs/PUBLIC_RELEASE_HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/verify_productization_status.py --format markdown", text)
        self.assertIn("python scripts/verify_first_run_readiness.py --format markdown", text)
        self.assertIn("python scripts/verify_public_demo_mode.py --format markdown", text)
        self.assertIn("python scripts/verify_comic_v2_delivery.py --format markdown", text)
        self.assertIn("python scripts/verify_comic_v2_downstream_handoff.py --format markdown", text)
        self.assertIn("python scripts/verify_research_office_readiness.py --format markdown", text)
        self.assertIn("python scripts/verify_release_readiness.py --format markdown", text)
        self.assertIn("python scripts/check_no_secrets.py", text)

    def test_readme_links_public_release_handoff_doc(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("docs/PUBLIC_RELEASE_HANDOFF.md", text)
        self.assertIn("公开发布给面试官、访客或新开发者前的交接说明", text)


if __name__ == "__main__":
    unittest.main()
