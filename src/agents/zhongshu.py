"""中书省 — Planner Agent: 理解需求、拆解任务、起草方案"""

import json
import dataclasses

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
    TaskPlan,
    PlanStep,
    ReviewResult,
)
from src.data.prompts import ZHONGSHU_SYSTEM_PROMPT


class ZhongshuAgent(BaseAgent):
    agent_id = AgentId.ZHONGSHU

    def _plan_to_text(self, plan: TaskPlan) -> str:
        """将方案转为紧凑的文本表示, 避免 Python repr 过大"""
        steps_text = "\n".join(
            f"  步骤{s.step_id}: [{s.assigned_to}] {s.action} — {s.detail}"
            f" (依赖: {s.depends_on or '无'}, 风险: {s.risk_level})"
            for s in plan.steps
        )
        return f"版本{plan.version}: {plan.title}\n步骤:\n{steps_text}"

    async def draft_plan(self, task_id: str, user_request: str, context: str = "", retry: int = 0) -> TaskPlan:
        """起草执行方案, 如果步骤为空自动重试最多2次"""
        prompt = f"""## 用户需求
{user_request}

## 吏部检索的上下文
{context or "（无额外上下文）"}

请根据以上信息起草 TaskPlan。输出 JSON 格式，steps 里每步的 assigned_to 请从以下选择:
- 兵部: 代码操作 (读/写/搜索/执行命令)
- 刑部: 测试/审查/安全扫描
- 吏部: 向量库查询
- 户部: 文件/数据操作
- 工部: 文档/报告生成

assigned_to 和 action 和 detail 字段务必用中文。
**重要: steps 不能为空, 至少需要1个步骤。**"""
        if "workplace-ready research package" in user_request or "研究报告" in user_request or "调研" in user_request:
            prompt += """

## 研究报告办公室补充要求
如果这是调研/研究报告任务，建议至少拆成以下步骤:
1. 兵部: 搜索并整理来源、近期数据点、图表建议。
2. 刑部: 审查来源质量、数据年份、是否存在占位数字或未核验结论。
3. 工部: 基于已验证材料生成老板可读报告。
可根据任务复杂度增加户部数据整理或礼部摘要包装步骤。"""

        result = await self.call_llm(prompt=prompt, output_schema=TaskPlan)
        steps = result.get("steps", [])
        if steps and isinstance(steps[0], dict):
            steps = [PlanStep(**s) for s in steps]
        plan = TaskPlan(
            task_id=task_id,
            version=1,
            title=result.get("title", user_request[:50]),
            steps=steps,
            estimated_tokens=result.get("estimated_tokens", 0),
            risk_summary=result.get("risk_summary", ""),
        )
        if not plan.steps and retry < 2:
            print(f"  [中书省] 方案步骤为空, 重试 ({retry+1}/2)...")
            return await self.draft_plan(task_id, user_request, context, retry + 1)
        return plan

    async def revise_plan(self, task_id: str, original_plan: TaskPlan, review: ReviewResult,
                          context: str = "", retry: int = 0) -> TaskPlan:
        """根据驳回意见修订方案, 空步骤时自动重试"""
        issues_text = "\n".join(
            f"- [步骤{i.step_id or '整体'}] [{i.severity}] {i.category}: {i.detail} (建议: {i.suggestion})"
            for i in review.issues
        ) or "（无具体问题）"
        changes_text = "\n".join(f"- {c}" for c in review.required_changes) or "（无具体修改要求）"

        # 用紧凑格式, 避免 dataclass repr 过大导致 JSON 截断
        plan_text = self._plan_to_text(original_plan)

        prompt = f"""## 原方案
{plan_text}

## 驳回意见
决议: {review.decision}
问题:
{issues_text}

要求修改:
{changes_text}

## 补充上下文
{context or "（无）"}

请修订方案，逐条回应驳回意见。输出 JSON 格式的修订后 TaskPlan，version 递增。
**重要: steps 不能为空, 至少需要1个步骤。保持简洁, 每步 detail 不超过100字。**"""

        result = await self.call_llm(prompt=prompt, output_schema=TaskPlan)
        steps = result.get("steps", [])
        if steps and isinstance(steps[0], dict):
            steps = [PlanStep(**s) for s in steps]
        plan = TaskPlan(
            task_id=task_id,
            version=original_plan.version + 1,
            title=result.get("title", original_plan.title),
            steps=steps,
            estimated_tokens=result.get("estimated_tokens", 0),
            risk_summary=result.get("risk_summary", ""),
        )
        if not plan.steps and retry < 2:
            print(f"  [中书省] 修订方案步骤为空, 重试 ({retry+1}/2)...")
            return await self.revise_plan(task_id, original_plan, review, context, retry + 1)
        return plan

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理收到的消息"""
        if msg.msg_type == MessageType.HANDOFF and msg.payload.get("action") == "review_result":
            # 被驳回 — 修订
            review = ReviewResult(**msg.payload.get("review", {}))
            # TBD: 从 payload 中获取原 plan
            return AgentMessage(
                id="",
                task_id=msg.task_id,
                from_agent=self.agent_id,
                to_agent=AgentId.MENXIA,
                msg_type=MessageType.HANDOFF,
                payload={"action": "revise", "status": "drafting"},
            )
        elif msg.msg_type == MessageType.QUERY:
            # 被要求起草
            user_request = msg.payload.get("request", "")
            plan = await self.draft_plan(msg.task_id, user_request)
            return AgentMessage(
                id="",
                task_id=msg.task_id,
                from_agent=self.agent_id,
                to_agent=AgentId.MENXIA,
                msg_type=MessageType.HANDOFF,
                payload={"action": "submit_plan", "plan": plan.__dict__},
            )
        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
