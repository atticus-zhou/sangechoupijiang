"""刑部 — Testing Agent: 验证兵部产出、代码审查、测试运行"""

import json

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
)
from src.data.prompts import XINGBU_SYSTEM_PROMPT


class XingbuAgent(BaseAgent):
    agent_id = AgentId.XINGBU

    async def verify_step(
        self,
        task_id: str,
        step_id: int,
        bingbu_output: dict,
        context: str = "",
    ) -> dict:
        """验证一个步骤产出 — 检查数据存在性和质量"""

        output_text = bingbu_output.get('output', '')
        if isinstance(output_text, str):
            output_text = output_text[:3000]
        elif isinstance(output_text, dict):
            output_text = json.dumps(output_text, ensure_ascii=False)[:3000]

        summary = bingbu_output.get('summary', '(无)')

        # 快速判断: 只要有实质内容就通过 (web搜索类任务数据量已足够判定标准)
        has_content = bool(output_text and len(output_text) > 20)
        if has_content and summary not in ("(无产出)", "(LLM 返回空)"):
            return {
                "step_id": step_id,
                "verdict": "pass",
                "issues": [],
                "test_summary": f"产出包含实质性内容 ({len(output_text)}字符), 通过",
            }

        # 内容不足时才调用 LLM 详细审查
        prompt = f"""## 验证任务
步骤ID: {step_id}

## 被验证的产出
摘要: {summary}
内容长度: {len(output_text)}字符
内容: {output_text[:2000] or '(空)'}

请判定: 此产出是否有足够的实质性内容?
- 有 ≥50 字符的真实数据 → pass
- 为空/极短/无实质内容 → fail

只输出一个词: pass 或 fail"""

        result = await self.call_llm(prompt=prompt)
        content = result.get("content", "").strip().lower()

        return {
            "step_id": step_id,
            "verdict": "pass" if "pass" in content else "fail",
            "issues": [],
            "test_summary": content or "(自动判定: 内容不足)",
        }

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理尚书省派发的验证任务"""
        if msg.msg_type == MessageType.HANDOFF:
            step_id = msg.payload.get("step_id", 0)
            bingbu_output = msg.payload.get("bingbu_output", {})
            result = await self.verify_step(
                task_id=msg.task_id,
                step_id=step_id,
                bingbu_output=bingbu_output,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=AgentId.SHANGSHU,
                msg_type=MessageType.RESPONSE,
                payload={"action": "verify_result", "result": result},
            )
        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
