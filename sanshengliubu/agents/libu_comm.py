"""礼部 — 📡 最终总装/格式化输出

礼部是三省六部流程的最后一环。在所有部门完成工作后，
礼部负责将零散的产出按格式、按顺序组装成最终文档。

职能:
- 最终总装: 按文档模板把各步骤产出拼成完整报告
- 格式管理: 标题层级、段落顺序、代码块、表格
- 多平台适配: 飞书消息卡片、微信 Markdown、GitHub PR、邮件
- 语言润色: 确保最终输出专业、通顺、无歧义
"""

from typing import Optional

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


# ============================================================
# 内置文档模板
# ============================================================

OUTPUT_TEMPLATES = {
    "bug_fix": {
        "title": "🐛 Bug 修复报告",
        "sections": [
            ("问题描述", "用户报告的原始问题"),
            ("根因分析", "定位到的根本原因"),
            ("修复方案", "具体的代码修改"),
            ("回归测试", "补加的测试用例及结果"),
            ("安全审查", "安全检查结果"),
            ("影响范围", "修改影响的模块和功能"),
            ("验证结果", "全量测试通过情况"),
        ],
        "footer": "---\n*本报告由三省六部自动生成 · 中书起草 · 门下审议 · 尚书调度 · 六部执行*",
    },
    "feature": {
        "title": "✨ 功能开发报告",
        "sections": [
            ("需求概述", "功能描述和背景"),
            ("设计方案", "技术方案和架构决策"),
            ("实现细节", "关键代码和 API 变更"),
            ("测试覆盖", "单元测试和集成测试"),
            ("文档更新", "需要更新的文档"),
            ("部署说明", "配置变更和部署步骤"),
        ],
        "footer": "---\n*本报告由三省六部自动生成 · 中书起草 · 门下审议 · 尚书调度 · 六部执行*",
    },
    "review": {
        "title": "🔍 代码审查报告",
        "sections": [
            ("审查范围", "审查的文件和模块"),
            ("问题列表", "发现的问题按严重程度排列"),
            ("安全风险", "安全问题详细说明"),
            ("性能问题", "性能瓶颈和建议"),
            ("规范问题", "代码风格和规范违规"),
            ("改进建议", "优化建议汇总"),
        ],
        "footer": "---\n*本报告由三省六部自动生成*",
    },
    "image_gen": {
        "title": "🖼️ 图片生成报告",
        "sections": [
            ("生成内容", "图片描述和用途"),
            ("图片类型", "柱状图/架构图/宣传图等"),
            ("生成参数", "使用的模型和参数"),
            ("图片预览", "图片链接"),
        ],
        "footer": "---\n*图片由工部使用 GPT-image 生成*",
    },
    "general": {
        "title": "📋 任务执行报告",
        "sections": [
            ("任务概述", "任务目标和范围"),
            ("执行步骤", "各步骤执行情况"),
            ("产出汇总", "最终产出摘要"),
        ],
        "footer": "---\n*本报告由三省六部自动生成*",
    },
}


LIBU_COMM_PROMPT = """你是礼部尚书，三省六部中的最终总装官。你是流程的最后一环。

## 核心职责: 最终总装
所有部门完成工作后，你把零散的产出组装成一份格式规范、结构清晰的最终文档。

## 你负责的内容
1. **格式管理**: 标题层级、段落顺序、代码块格式、表格排版
2. **顺序编排**: 按逻辑顺序排列各步骤产出
3. **多平台适配**:
   - GitHub PR: Markdown 格式，含 summary 和 checklist
   - 飞书消息: 飞书卡片格式，支持富文本
   - 微信: 简洁 Markdown
   - 邮件: HTML 格式（未来）
4. **质量把关**: 确保最终输出没有明显错误、格式统一

## 工作方式
收到尚书省的格式化请求后:
1. 识别任务类型 (bug_fix/feature/review/image_gen/general)
2. 套用对应的文档模板
3. 把各步骤的产出填入对应章节
4. 输出格式化后的最终文档

## 你不管的事
- 不执行代码操作 (那是兵部的事)
- 不验证对错 (那是刑部的事)
- 不生成图片 (那是工部的事)
- 你只管排版、格式、顺序"""


class LibuCommAgent(AutonomousAgent):

    @property
    def speaker(self) -> Speaker:
        return Speaker.LIBU_COMM

    @property
    def system_prompt(self) -> str:
        return LIBU_COMM_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        if msg.msg_type == MessageType.FORMAT_OUTPUT:
            return await self._assemble_final_output(msg)

        if msg.msg_type == MessageType.EXTERNAL_COM:
            return await self._external_communication(msg)

        return None

    async def _assemble_final_output(self, msg: CourtMessage) -> CourtMessage:
        """最终总装——把所有产出拼成格式化的最终文档"""
        task_type = msg.payload.get("task_type", "general")
        plan_title = msg.payload.get("plan_title", "")
        step_results = msg.payload.get("step_results", [])
        final_report_text = msg.payload.get("final_report", "")
        platform = msg.payload.get("platform", "markdown")

        self.log_event("总装", f"任务类型: {task_type}, 产出步骤: {len(step_results)}")

        # 1. 选择模板
        template = OUTPUT_TEMPLATES.get(task_type, OUTPUT_TEMPLATES["general"])

        # 2. 组装文档
        lines = []
        lines.append(f"# {template['title']}")
        if plan_title:
            lines.append(f"> 任务: {plan_title}")
        lines.append("")

        # 3. 各章节
        for section_title, section_desc in template["sections"]:
            lines.append(f"## {section_title}")
            lines.append("")

            # 从步骤结果中找相关内容
            section_content = self._find_section_content(section_title, step_results, final_report_text)
            if section_content:
                lines.append(section_content)
            else:
                lines.append(f"*（{section_desc} — 待填充）*")

            lines.append("")

        # 4. 执行摘要
        lines.append("## 执行过程")
        lines.append("")
        for i, step in enumerate(step_results, 1):
            status_icon = "✅" if step.get("status") == "done" else "❌"
            summary = step.get("summary", "无描述")
            lines.append(f"{i}. {status_icon} {summary}")

        lines.append("")
        lines.append(template["footer"])

        # 5. 平台适配
        formatted = "\n".join(lines)
        if platform == "feishu":
            formatted = self._adapt_for_feishu(formatted)
        elif platform == "wechat":
            formatted = self._adapt_for_wechat(formatted)

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.OUTPUT_READY,
            content=formatted,
            payload={
                "formatted": formatted,
                "task_type": task_type,
                "platform": platform,
                "template_used": template["title"],
                "sections_count": len(template["sections"]),
            },
            reply_to=msg.id,
        )

    async def _external_communication(self, msg: CourtMessage) -> CourtMessage:
        """外部通信"""
        platform = msg.payload.get("platform", "unknown")
        self.log_event("外部通信", f"平台: {platform}")
        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.RESPONSE,
            content=f"📡 礼部已通过 {platform} 发送通信。",
            payload={"platform": platform, "status": "sent"},
            reply_to=msg.id,
        )

    def _find_section_content(self, section_title: str, step_results: list, final_report: str) -> str:
        """从步骤结果中找到属于某个章节的内容"""
        # 关键词匹配
        keywords = {
            "问题描述": ["问题", "描述", "需求", "bug", "issue"],
            "根因分析": ["根因", "原因", "定位", "分析", "root cause"],
            "修复方案": ["修复", "修改", "fix", "方案", "优化", "实施"],
            "回归测试": ["回归", "测试", "test", "用例"],
            "安全审查": ["安全", "security", "注入", "xss"],
            "影响范围": ["影响", "范围", "模块", "依赖"],
            "验证结果": ["验证", "通过", "pass", "测试结果"],
            "需求概述": ["需求", "概述", "背景", "目标"],
            "设计方案": ["设计", "方案", "架构", "技术"],
            "实现细节": ["实现", "代码", "api", "接口"],
            "测试覆盖": ["测试", "覆盖", "单元测试", "集成测试"],
            "生成内容": ["图片", "生成", "image", "描述"],
        }

        matching_keywords = keywords.get(section_title, [section_title.lower()])

        # 从步骤结果中匹配
        for step in step_results:
            summary = step.get("summary", "")
            detail = step.get("detail", {})
            if any(kw in summary.lower() for kw in matching_keywords):
                return summary

        # 从最终报告中截取
        if final_report and any(kw in final_report.lower() for kw in matching_keywords):
            return final_report[:500]

        return ""

    def _adapt_for_feishu(self, markdown: str) -> str:
        """适配飞书消息格式"""
        return f"[飞书卡片格式]\n{markdown}"

    def _adapt_for_wechat(self, markdown: str) -> str:
        """适配微信消息格式"""
        return f"[微信格式]\n{markdown}"

    @classmethod
    def get_available_templates(cls) -> dict:
        """获取所有文档模板"""
        return {
            k: {"title": v["title"], "sections": [s[0] for s in v["sections"]]}
            for k, v in OUTPUT_TEMPLATES.items()
        }
