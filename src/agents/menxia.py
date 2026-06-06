"""门下省 — Reviewer Agent: 审查方案可行性、完备性、风险"""

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
    TaskPlan,
    ReviewResult,
)
from src.data.prompts import MENXIA_SYSTEM_PROMPT


class MenxiaAgent(BaseAgent):
    agent_id = AgentId.MENXIA

    async def review_plan(self, task_id: str, plan: TaskPlan, history_context: str = "") -> ReviewResult:
        """审议方案"""
        steps_text = "\n".join(
            f"  步骤{s.step_id}: [{s.assigned_to}] {s.action} — {s.detail} "
            f"(依赖: {s.depends_on or '无'}, 风险: {s.risk_level})"
            for s in plan.steps
        )

        prompt = f"""## 待审议方案 (v{plan.version})
标题: {plan.title}
预估 tokens: {plan.estimated_tokens}
风险摘要: {plan.risk_summary}

步骤列表:
{steps_text}

## 历史案例参考
{history_context or "（无相关历史案例）"}

请审查此方案。从可行性、完备性、风险三个维度分析，给出你的决议。"""

        result = await self.call_llm(prompt=prompt, output_schema=ReviewResult)
        from src.data.schemas import ReviewIssue
        issues = result.get("issues", [])
        if issues and isinstance(issues[0], dict):
            issues = [ReviewIssue(**i) for i in issues]
        review = ReviewResult(
            task_id=task_id,
            plan_version=plan.version,
            decision=result.get("decision", "approve"),
            issues=issues,
            required_changes=result.get("required_changes", []),
            confidence=result.get("confidence", 0.8),
        )
        return review

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理收到的消息"""
        if msg.msg_type == MessageType.HANDOFF and msg.payload.get("action") == "submit_plan":
            plan = TaskPlan(**msg.payload.get("plan", {}))
            review = await self.review_plan(msg.task_id, plan)
            return AgentMessage(
                id="",
                task_id=msg.task_id,
                from_agent=self.agent_id,
                to_agent=AgentId.SHANGSHU if review.decision == "approve" else AgentId.ZHONGSHU,
                msg_type=MessageType.DECISION,
                payload={
                    "action": "review_result",
                    "review": review.__dict__,
                    "plan": plan.__dict__,
                },
            )
        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
