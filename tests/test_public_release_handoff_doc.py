from pathlib import Path
import unittest


class PublicReleaseHandoffDocTests(unittest.TestCase):
    def test_public_release_handoff_doc_exists_and_sets_boundaries(self):
        text = Path("docs/PUBLIC_RELEASE_HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("/api/demo/public-showcase", text)
        self.assertIn("dist/public-showcase", text)
        self.assertIn("handoff manifest", text)
        self.assertIn("data/comic_production_claim_report.json", text)
        self.assertIn("claim_upgrade_recovery", text)
        self.assertIn("public_recovery_drill", text)
        self.assertIn("downstream_handoff_decision", text)
        self.assertIn("regenerate_images", text)
        self.assertIn("fixture_only", text)
        self.assertIn("preserve_policy", text)
        self.assertIn("clear_policy", text)
        self.assertIn("AI 漫剧 Word 制片画布", text)
        self.assertIn("七份下载物", text)
        self.assertIn("最快验收路线", text)
        self.assertIn("核对 handoff manifest", text)
        self.assertIn("研究办公室阶段性交付声明", text)
        self.assertIn("下游生产 quick-start", text)
        self.assertIn("待补证据交接表", text)
        self.assertIn("API Key", text)
        self.assertIn("SaaS", text)
        self.assertIn("FastAPI", text)
        self.assertIn("npm run check:online", text)
        self.assertIn("https://www.atticus.asia/three-stooges/", text)
        self.assertIn("Vercel authorization/redeploy", text)
        self.assertIn("Public Asset Requirement Matrix", text)
        self.assertIn("portfolio_embed.asset_requirement_matrix", text)
        self.assertIn("核对资产图片规格矩阵", text)
        self.assertIn("资产使用地图", text)
        self.assertIn("asset_usage_map", text)
        self.assertIn("handoff_ready=true", text)
        self.assertIn("three_view", text)
        self.assertIn("expression_sheet", text)
        self.assertIn("turnaround", text)
        self.assertIn("top_down", text)
        self.assertIn("npm run check:showcase", text)
        self.assertIn("python scripts/verify_portfolio_showcase_sync.py --format markdown", text)
        self.assertIn("--target-dir", text)
        self.assertIn(".github/workflows/release-readiness.yml", text)
        self.assertIn("GitHub Actions", text)
        self.assertIn("no-key-release-evidence", text)

    def test_public_release_handoff_doc_lists_required_release_gates(self):
        text = Path("docs/PUBLIC_RELEASE_HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/verify_productization_status.py --format markdown", text)
        self.assertIn("python scripts/verify_first_run_readiness.py --format markdown", text)
        self.assertIn("python scripts/verify_public_demo_mode.py --format markdown", text)
        self.assertIn("python scripts/export_public_showcase.py", text)
        self.assertIn("python scripts/verify_static_public_showcase.py --format markdown", text)
        self.assertIn("python scripts/verify_portfolio_showcase_sync.py --format markdown", text)
        self.assertIn("python scripts/verify_comic_real_production_claim.py --format markdown", text)
        self.assertIn("python scripts/verify_comic_v2_delivery.py --format markdown", text)
        self.assertIn("python scripts/verify_comic_v2_downstream_handoff.py --format markdown", text)
        self.assertIn("python scripts/verify_research_office_readiness.py --format markdown", text)
        self.assertIn("python scripts/verify_release_readiness.py --format markdown", text)
        self.assertIn("python scripts/verify_github_release_evidence.py --format markdown", text)
        self.assertIn("python scripts/check_no_secrets.py", text)
        self.assertIn(".github/workflows/release-readiness.yml", text)
        self.assertIn("no-key-release-evidence", text)
        self.assertIn("GitHub 公共 API", text)
        self.assertIn("npm run prepare:vercel-prebuilt", text)

    def test_downstream_handoff_doc_explains_operator_decision_card(self):
        text = Path("docs/COMIC_DOWNSTREAM_HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("downstream_handoff_decision", text)
        self.assertIn("structure_demo_only", text)
        self.assertIn("ready_for_downstream", text)
        self.assertIn("blocked", text)
        self.assertIn("handoff_allowed=false", text)
        self.assertIn("不能把当前制片包说成", text)
        self.assertIn("Libtv、小云雀", text)

    def test_readme_links_public_release_handoff_doc(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("docs/PUBLIC_RELEASE_HANDOFF.md", text)
        self.assertIn("claim_upgrade_recovery", text)
        self.assertIn("公开演示和部署边界", text)
        self.assertIn("不要把自己的 API Key 暴露给访问者", text)


if __name__ == "__main__":
    unittest.main()
