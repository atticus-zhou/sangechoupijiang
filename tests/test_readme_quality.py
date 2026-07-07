from pathlib import Path
import unittest


class ReadmeQualityTests(unittest.TestCase):
    def test_readme_is_readable_chinese_and_current_for_comic_v2(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertNotIn("锟", text)
        self.assertNotIn("�", text)
        self.assertNotIn("涓変", text)
        self.assertIn("三个臭皮匠", text)
        self.assertIn("AI 漫剧制片办公室", text)
        self.assertIn("确认故事后默认进入 V2 制片链", text)
        self.assertIn("启动检查", text)
        self.assertIn("模型页面", text)
        self.assertIn("测试按钮", text)
        self.assertIn("制片追溯", text)
        self.assertIn("故事版本", text)
        self.assertIn("资产版本", text)
        self.assertIn("视觉质检", text)
        self.assertIn("使用者填写自己的 Key", text)
        self.assertIn("python scripts/verify_comic_v2_delivery.py", text)
        self.assertIn("python scripts/verify_comic_v2_user_flow.py", text)
        self.assertIn("tests/fixtures/comic_v2_sample.json", text)
        self.assertIn("tests/fixtures/research_sample.json", text)
        self.assertIn("python -m unittest tests.test_sample_project_fixtures -q", text)
        self.assertIn("config.yaml", text)
        self.assertIn("不会提交到 GitHub", text)
        self.assertIn("docs/DEPLOYMENT_MODES.md", text)

    def test_deployment_modes_doc_separates_demo_local_and_saas(self):
        text = Path("docs/DEPLOYMENT_MODES.md").read_text(encoding="utf-8")

        self.assertNotIn("锟", text)
        self.assertNotIn("�", text)
        self.assertIn("演示模式", text)
        self.assertIn("本地真实模式", text)
        self.assertIn("未来 SaaS 模式", text)
        self.assertIn("不要把个人 API Key 写入前端", text)
        self.assertIn("Vercel", text)


if __name__ == "__main__":
    unittest.main()
