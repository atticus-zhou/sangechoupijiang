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

    def test_future_long_goal_defines_product_north_star_and_milestones(self):
        text = Path("docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8")

        self.assertIn("### 后续长目标：从办公室样板到产品网络", text)
        self.assertIn("长期北极星", text)
        self.assertIn("不是把每个 Agent 做成聊天框", text)
        self.assertIn("第一里程碑：一个办公室真实可交付", text)
        self.assertIn("第二里程碑：办公室协议成为底座", text)
        self.assertIn("第三里程碑：多办公室组合协作", text)
        self.assertIn("先让一个复杂项目被稳定完成，再让多个办公室协同完成更大的项目", text)

    def test_office_isolation_verifier_is_part_of_platform_protocol(self):
        text = Path("docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/verify_office_isolation.py --format markdown", text)
        self.assertIn("payload.workspace_id", text)

    def test_download_links_are_marked_done_with_launch_gate_evidence(self):
        text = Path("docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8")

        self.assertIn("- [x] 下载链接必须可用。", text)
        self.assertIn("evidence_links", text)
        self.assertIn("/api/offices/{office_id}/launch-gates", text)
        self.assertIn("/api/demo/comic-production/files/word_canvas.docx", text)
        self.assertIn("/api/demo/research/files/report.md", text)

    def test_phase_d_real_use_loop_is_fully_checked(self):
        lines = Path("docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8").splitlines()

        start = next(i for i, line in enumerate(lines) if line.startswith("### 阶段 D："))
        phase_lines = []
        for line in lines[start + 1:]:
            if line.startswith("### "):
                break
            phase_lines.append(line)

        checks = [line[:5] for line in phase_lines if line.startswith("- [")]
        self.assertEqual(["- [x]", "- [x]", "- [x]", "- [x]", "- [x]"], checks)

    def test_product_principles_lock_main_office_strategy(self):
        text = Path("docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8")

        self.assertIn("- [x] 不再盲目横向增加办公室；先把一个主力办公室打磨到能展示、能试用、能交付。", text)
        self.assertIn("- [x] 默认主力办公室为 `AI漫剧制片办公室`，研究办公室保持可用但不作为当前主打。", text)

    def test_stage_a_trusted_showcase_documents_readme_and_safety(self):
        text = Path("docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8")

        self.assertIn("- [x] GitHub README 能让面试官、开发者和普通用户分别看懂怎么体验、怎么运行、怎么扩展。", text)
        self.assertIn("- [x] 所有公开展示都不暴露 API Key、Cookie、登录态、用户数据和运行产物。", text)

    def test_stage_b_single_office_product_loop_is_checked(self):
        text = Path("docs/PRODUCT_EVOLUTION_TASKLIST.md").read_text(encoding="utf-8")

        self.assertIn("- [x] 用户可从灵感、完整剧本、已有角色设定、参考风格进入工作流。", text)
        self.assertIn("- [x] 内阁只负责和人对齐故事，不替三省六部做生产拆解。", text)
        self.assertIn("- [x] 三省六部必须产出可审核的故事合同、视觉母版、资产清单、镜头执行卡、提示词包和 Word 制片画布。", text)
        self.assertIn("- [x] 用户能在关键节点确认、修改、退回，退回意见必须真实影响下一版结果。", text)
        self.assertIn("- [x] 最终 Word 画布能被下游图片/视频工具理解，而不是只适合展示给人看。", text)
        self.assertIn("阶段 B 产品闭环", text)


if __name__ == "__main__":
    unittest.main()
