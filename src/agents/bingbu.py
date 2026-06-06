"""兵部 — Execution Agent: 代码操作、文件读写、Shell执行"""

import json

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
)
from src.data.prompts import BINGBU_SYSTEM_PROMPT


class BingbuAgent(BaseAgent):
    agent_id = AgentId.BINGBU

    async def execute_step(
        self,
        task_id: str,
        step_id: int,
        instruction: str,
        context: str = "",
    ) -> dict:
        """执行一个步骤 — 使用 web_search/web_fetch 获取真实数据"""

        from dataclasses import dataclass, field

        @dataclass
        class SourceItem:
            title: str = ""
            url: str = ""
            publisher: str = ""
            published_at: str = ""
            note: str = ""

        @dataclass
        class DataPoint:
            metric: str = ""
            value: str = ""
            period: str = ""
            source_url: str = ""
            confidence: str = "medium"
            note: str = ""

        @dataclass
        class ChartSuggestion:
            title: str = ""
            chart_type: str = ""
            purpose: str = ""
            data_needed: str = ""

        @dataclass
        class CompetitorItem:
            product_name: str = ""
            brand: str = ""
            sales: str = ""
            price: str = ""
            selling_points: str = ""
            target_user: str = ""
            positive_keywords: str = ""
            negative_pain_points: str = ""

        @dataclass
        class BingbuOutput:
            status: str = "completed"
            summary: str = ""
            output: str = ""
            data_sources: list[str] = field(default_factory=list)
            sources: list[SourceItem] = field(default_factory=list)
            data_points: list[DataPoint] = field(default_factory=list)
            chart_suggestions: list[ChartSuggestion] = field(default_factory=list)
            competitors: list[CompetitorItem] = field(default_factory=list)
            notes: str = ""

        prompt = f"""## 执行任务
步骤ID: {step_id}
指令: {instruction}

你在研究报告办公室担任资料与数据收集员。请用 web_search / web_fetch 收集真实资料，然后调用 output 返回结构化结果。

工作要求:
1. 搜索 2-4 组不同关键词，优先找近期、权威、可引用来源。
2. 如有必要，抓取 1-2 个关键页面。
3. 不要编造具体数字。无法确认的数字请写“待核验”，并在 notes 中说明。
4. data_sources 填 URL 字符串列表。
5. sources 填来源明细，包含 title/url/publisher/published_at/note。
6. data_points 填可用于报告或图表的数据点，包含 metric/value/period/source_url/confidence/note。
7. chart_suggestions 填适合老板汇报的图表建议。
8. competitors 尽量填 Top 竞品字段: product_name/brand/sales/price/selling_points/target_user/positive_keywords/negative_pain_points。
9. output 写成可交给工部继续写报告的资料简报，必须包含“来源摘录”“数据要点”“竞品要点”“图表建议”四个小节。

重要: 搜索足够后必须调用 output，不要无限搜索。"""

        prompt += """

补充规则：
- 如果任务涉及飞瓜、抖音数据、截图、取证、榜单截图，优先使用 browser_capture_feigua_plan 自动截图。
- 如果页面难以抓取、JS 动态加载、疑似反爬或页面结构变化，优先使用 scrapling_feigua_collect / scrapling_scrape_url；抓不到结构化数据时再截图兜底。
- 如果用户尚未登录飞瓜，先调用 browser_start_login 打开本地登录窗口，并在 notes 中说明需要用户完成登录后重试。
- 截图工具返回的图片 path 必须写入 data_sources 或 notes，并在 output 中增加“截图证据”小节。
"""

        result = await self.call_llm(
            prompt=prompt,
            output_schema=BingbuOutput,
            tool_names=[
                "web_search",
                "web_fetch",
                "browser_start_login",
                "browser_capture_url",
                "browser_capture_feigua_plan",
                "scrapling_status",
                "scrapling_scrape_url",
                "scrapling_capture_url",
                "scrapling_feigua_collect",
            ],
        )

        # 结构化结果
        status = result.get("status", "completed")
        summary = result.get("summary", "")
        output = result.get("output", "")

        # 兜底: 如果 output 为空但 summary 有内容, 用 summary 作为 output
        if not output and summary:
            output = summary
        # 如果都为空, 检查 content
        if not output and not summary:
            content = result.get("content", "")
            if content:
                output = content
                summary = content[:200]

        has_data = bool(output and len(str(output)) > 20)
        return {
            "step_id": step_id,
            "status": status if has_data else "failed",
            "summary": summary or "(无产出)",
            "output": output or "(空)",
            "files_examined": [],
            "files_to_modify": [],
            "context_refs": result.get("data_sources", []),
            "sources": result.get("sources", []),
            "data_points": result.get("data_points", []),
            "chart_suggestions": result.get("chart_suggestions", []),
            "competitors": result.get("competitors", []),
            "notes": result.get("notes", ""),
        }

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理尚书省派发的执行任务"""
        if msg.msg_type == MessageType.HANDOFF:
            step_id = msg.payload.get("step_id", 0)
            instruction = msg.payload.get("instruction", "")
            result = await self.execute_step(
                task_id=msg.task_id,
                step_id=step_id,
                instruction=instruction,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=AgentId.SHANGSHU,
                msg_type=MessageType.RESPONSE,
                payload={"action": "step_result", "result": result},
            )
        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
