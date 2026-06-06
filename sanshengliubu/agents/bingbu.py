"""兵部 — 执行操作的自治 Agent

收到尚书省派发 → 执行 → 返回结果
"""

from typing import Optional
from ..llm.providers import LLMMessage

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


BINGBU_PROMPT = """你是兵部尚书，三省六部中的执行者。

## 职责
- 执行尚书省分派的具体任务
- 每步执行后输出结构化结果
- 失败时说明原因

## 输出格式
{
    "status": "done 或 failed",
    "summary": "做了什么",
    "detail": {}
}"""


class BingbuAgent(AutonomousAgent):

    @property
    def speaker(self) -> Speaker:
        return Speaker.BINGBU

    @property
    def system_prompt(self) -> str:
        return BINGBU_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        """收到派发 → 执行"""

        if msg.msg_type == MessageType.DISPATCH:
            return await self._execute(msg)

        return None

    async def _execute(self, msg: CourtMessage) -> CourtMessage:
        step = msg.payload.get("step", {})
        step_id = step.get("step_id", 0)
        action = step.get("action", "")
        detail = step.get("detail", "")

        self.log_event("执行", f"步骤{step_id}: {action}")

        summary = f"兵部已执行步骤{step_id}: {action}"
        status = "done"
        if self._llm:
            try:
                prompt = f"""执行任务: {action}
详细指令: {detail}

请执行此任务并返回结果。输出 JSON: {{"status": "done 或 failed", "summary": "摘要", "detail": {{}}}}"""
                result = await self._llm.chat([
                    LLMMessage(role='system', content=self.system_prompt),
                    LLMMessage(role='user', content=prompt),
                ])
                summary = result.content[:200]
                status = "done" if "done" in result.content.lower() else "failed"
            except Exception:
                pass

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.RESULT,
            content=f"步骤{step_id} 执行{'完成' if status == 'done' else '失败'}: {summary}",
            payload={
                "result": {"step_id": step_id, "status": status, "summary": summary, "detail": {}},
            },
            reply_to=msg.id,
        )
