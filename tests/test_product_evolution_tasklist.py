from pathlib import Path
import unittest


class ProductEvolutionTasklistTests(unittest.TestCase):
    def test_long_term_goal_keeps_product_level_direction(self):
        text = Path("docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8")

        self.assertIn("### 后续长目标：从能跑到能交付", text)
        self.assertIn("陌生用户拿到产品后", text)
        self.assertIn("AI 漫剧制片办公室为主样板", text)
        self.assertIn("抽象成平台底座", text)
        self.assertIn("可展示、可试用、可交付、可追溯", text)
        self.assertIn("不新增大规模办公室", text)
        self.assertIn("不把本地 API Key、Cookie、登录态、运行历史和生成文件带入 Git 或公开部署", text)


if __name__ == "__main__":
    unittest.main()
