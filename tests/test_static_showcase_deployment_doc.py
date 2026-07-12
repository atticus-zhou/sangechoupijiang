from pathlib import Path
import unittest


class StaticShowcaseDeploymentDocTests(unittest.TestCase):
    def test_deployment_doc_has_a_real_backend_free_path(self):
        text = Path("docs/STATIC_SHOWCASE_DEPLOYMENT.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/export_public_showcase.py", text)
        self.assertIn("python scripts/verify_static_public_showcase.py --format markdown", text)
        self.assertIn("dist/public-showcase/index.html", text)
        self.assertIn("npx vercel --prod --cwd dist/public-showcase", text)
        self.assertIn("不需要 Python 后端", text)
        self.assertIn("不要把下面内容复制进静态展示目录", text)

    def test_readme_links_the_static_deployment_path(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("docs/STATIC_SHOWCASE_DEPLOYMENT.md", text)
        self.assertIn("python scripts/export_public_showcase.py", text)
        self.assertIn("dist/public-showcase/index.html", text)


if __name__ == "__main__":
    unittest.main()
