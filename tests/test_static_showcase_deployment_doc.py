from pathlib import Path
import unittest


class StaticShowcaseDeploymentDocTests(unittest.TestCase):
    def test_deployment_doc_has_a_real_backend_free_path(self):
        text = Path("docs/STATIC_SHOWCASE_DEPLOYMENT.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/export_public_showcase.py", text)
        self.assertIn("python scripts/verify_static_public_showcase.py --format markdown", text)
        self.assertIn("dist/public-showcase/index.html", text)
        self.assertIn("npx vercel --prod --cwd dist/public-showcase", text)
        self.assertIn("portfolio-deploy-manifest.json", text)
        self.assertIn("data/visitor_acceptance_guide.json", text)
        self.assertIn("Visitor Acceptance Guide", text)
        self.assertIn("npm run ship:vercel", text)
        self.assertIn("npm run check:online", text)
        self.assertIn("five-step visitor path", text)
        self.assertIn("eight reviewable downloads", text)
        self.assertIn("/three-stooges/", text)
        self.assertIn("data/comic_production_claim_report.json", text)
        self.assertIn("claim_upgrade_recovery", text)
        self.assertIn("regenerate_images", text)
        self.assertIn("三条首次使用路径", text)
        self.assertIn("public_demo", text)
        self.assertIn("local_real_use", text)
        self.assertIn("developer_extension", text)
        self.assertIn("不需要 API Key", text)
        self.assertIn("自己的 API Key", text)
        self.assertIn("避免模型配置、工作区、历史和产物串线", text)
        self.assertIn("不需要 Python 后端", text)
        self.assertIn("七份样例下载物", text)
        self.assertIn("最快验收路线", text)
        self.assertIn("八个可复核文件目录", text)
        self.assertIn("研究办公室阶段性交付声明", text)
        self.assertIn("下游生产 quick-start", text)
        self.assertIn("不要把下面内容复制进静态展示目录", text)

        self.assertIn("Asset Requirement Matrix In The Static Package", text)
        self.assertIn("asset_requirement_matrix", text)
        self.assertIn("核对资产图片规格矩阵", text)
        self.assertIn("three_view", text)
        self.assertIn("top_down", text)
        self.assertIn("npm run check:showcase", text)

    def test_readme_links_the_static_deployment_path(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("docs/STATIC_SHOWCASE_DEPLOYMENT.md", text)
        self.assertIn("python scripts/export_public_showcase.py", text)
        self.assertIn("dist/public-showcase/index.html", text)
        self.assertIn("claim_upgrade_recovery", text)


if __name__ == "__main__":
    unittest.main()
