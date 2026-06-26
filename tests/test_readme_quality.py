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
        self.assertIn("python scripts/verify_comic_v2_delivery.py", text)
        self.assertIn("python scripts/verify_comic_v2_user_flow.py", text)
        self.assertIn("config.yaml", text)
        self.assertIn("不会提交到 GitHub", text)


if __name__ == "__main__":
    unittest.main()
