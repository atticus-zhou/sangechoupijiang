"""刑部 — 验证产出的自治 Agent

收到尚书省验证请求 → 审查/测试 → 返回裁决
"""

import json
from typing import Optional
from ..llm.providers import LLMMessage

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


XINGBU_PROMPT = """你是刑部尚书，三省六部中的验证者。

## 职责
- 验证兵部的产出
- 裁决: pass(通过) 或 fail(不通过，需修复)
- fail 时必须说明具体问题

## 输出格式
{
    "verdict": "pass 或 fail",
    "issues": [],
    "summary": ""
}"""


class XingbuAgent(AutonomousAgent):

    @property
    def speaker(self) -> Speaker:
        return Speaker.XINGBU

    @property
    def system_prompt(self) -> str:
        return XINGBU_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        """收到验证请求 → 审查"""

        if msg.msg_type == MessageType.VERIFY:
            return await self._verify(msg)

        return None

    async def _verify(self, msg: CourtMessage) -> CourtMessage:
        bingbu_output = msg.payload.get("bingbu_output", {})
        step = msg.payload.get("step", {})
        step_id = step.get("step_id", bingbu_output.get("step_id", 0))

        self.log_event("验证", f"步骤{step_id}")

        verdict = "pass"
        content = f"步骤{step_id} 验证通过。"
        if self._llm:
            try:
                bingbu_summary = bingbu_output.get("summary", "")
                prompt = f"""验证兵部步骤{step_id}的产出:
{json.dumps(bingbu_output, ensure_ascii=False)[:2000]}

请审查并输出裁决。"""
                result = await self._llm.chat([
                    LLMMessage(role='system', content=self.system_prompt),
                    LLMMessage(role='user', content=prompt),
                ])
                content = result.content
                verdict = "pass" if "pass" in content.lower() else "fail"
            except Exception:
                pass

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.VERDICT,
            content=f"步骤{step_id} 验证{'通过' if verdict == 'pass' else '失败'}: {content[:200]}",
            payload={"result": {"status": "done" if verdict == "pass" else "failed", "summary": content}},
            reply_to=msg.id,
        )
