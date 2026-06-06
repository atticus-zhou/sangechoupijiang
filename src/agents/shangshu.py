"""尚书省 — Orchestrator Agent: LLM驱动调度, 每步决策"""

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
    TaskPlan,
    OrchestratorDecision,
)
from src.data.prompts import SHANGSHU_SYSTEM_PROMPT


class ShangshuAgent(BaseAgent):
    agent_id = AgentId.SHANGSHU

    async def decide_next(
        self,
        task_id: str,
        plan: TaskPlan,
        completed_steps: list[dict],
        in_progress_steps: list[dict],
        last_error: str = "",
        loop_count: int = 0,
    ) -> OrchestratorDecision:
        """做出下一步调度决策"""

        completed_text = "\n".join(
            f"  - 步骤{s['step_id']}: [{s.get('assigned_to', '?')}] {s.get('action', '?')} "
            f"→ 状态: {s.get('status', '?')}, 结果: {s.get('result_summary', '无')}"
            for s in completed_steps
        ) or "（无已完成步骤）"

        in_progress_text = "\n".join(
            f"  - 步骤{s['step_id']}: [{s.get('assigned_to', '?')}] {s.get('action', '?')} "
            f"→ 状态: {s.get('status', '?')}"
            for s in in_progress_steps
        ) or "（无执行中步骤）"

        # 列出所有步骤状态
        all_steps_text = "\n".join(
            f"  步骤{s.step_id}: [{s.assigned_to}] {s.action} — 状态: {s.status} "
            f"(依赖: {s.depends_on or '无'})"
            for s in plan.steps
        )

        prompt = f"""## 当前任务上下文
- 任务ID: {task_id}
- 任务标题: {plan.title}
- 方案总步骤数: {len(plan.steps)}

## 全部步骤状态
{all_steps_text}

## 已完成步骤
{completed_text}

## 执行中的步骤
{in_progress_text}

## 最近错误
{last_error or "（无错误）"}

## 当前循环
调度循环次数: {loop_count}

请做出下一步决策。记住兵部-刑部串行规则: 兵部执行任一步骤后必须安排刑部验证，通过后才能推进下一步。"""

        result = await self.call_llm(prompt=prompt, output_schema=OrchestratorDecision)
        from src.data.schemas import DecisionTarget
        targets = result.get("targets", [])
        if targets and isinstance(targets[0], dict):
            targets = [DecisionTarget(**t) for t in targets]
        decision = OrchestratorDecision(
            task_id=task_id,
            decision=result.get("decision", "WAIT"),
            targets=targets,
            reasoning=result.get("reasoning", ""),
            risk_assessment=result.get("risk_assessment", ""),
            veto_target=result.get("veto_target", ""),
            needs_human=result.get("needs_human", False),
        )
        return decision

    async def finalize(self, task_id: str, plan: TaskPlan, all_results: list[dict]) -> str:
        """汇总所有产出，生成最终报告"""
        results_text = "\n".join(
            f"  - 步骤{r.get('step_id', '?')}: {r.get('status', '?')} — {r.get('summary', '无')}"
            for r in all_results
        ) or "（无步骤）"

        prompt = f"""## 最终报告生成
任务ID: {task_id}
方案标题: {plan.title}
总步骤数: {len(plan.steps)}

## 执行结果
{results_text}

你是尚书令，任务已全部执行完毕。请汇总为一份**最终报告**。这不是决策，不需要再调度。
直接输出报告文本，包含:
1. 任务摘要
2. 每步执行情况
3. 关键产出
4. 后续建议"""

        result = await self.call_llm(prompt=prompt)
        return result.get("content", "无法生成最终报告")

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理收到的消息"""
        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
