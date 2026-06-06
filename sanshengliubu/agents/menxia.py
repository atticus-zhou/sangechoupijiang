"""门下省 — 审议方案的自治 Agent

收到中书省方案 → 审查可行性/完备性/风险 → 附议(批准)或封驳(驳回)
批准后通知尚书省开始执行。
"""

import json
from typing import Optional
from ..llm.providers import LLMMessage

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


MENXIA_PROMPT = """你是门下侍中，三省六部中的审议官。

## 职责
- 审查中书省(zhongshu)的方案
- 从三个维度审查: 可行性(能做吗) / 完备性(漏步骤了吗) / 风险(会出什么事)
- 做出决议: 附议(approve，批准) 或 封驳(reject，驳回)

## 审查原则
- 看到明显疏漏必须驳回，不能放水
- 驳回时必须给出具体问题和修改建议
- 如果方案大体可行但有细节问题，可以先驳回让中书省修订一轮
- 对方修订后确实改好了，就批准
- 不要吹毛求疵，只提实质性问题

## 输出格式
{
    "decision": "approve 或 reject",
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}"""


class MenxiaAgent(AutonomousAgent):

    @property
    def speaker(self) -> Speaker:
        return Speaker.MENXIA

    @property
    def system_prompt(self) -> str:
        return MENXIA_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        """自主处理消息"""

        # 收到中书省方案 → 审议
        if msg.msg_type == MessageType.DRAFT_PLAN:
            return await self._review_plan(msg)

        return None

    async def _review_plan(self, msg: CourtMessage) -> CourtMessage:
        """审议方案并做出裁决"""
        plan_content = msg.content
        plan_data = msg.payload

        decision = "approve"
        issues = []
        suggestions = []
        review_text = "臣门下侍中审议：方案可行。附议批准。"
        if self._llm:
            try:
                prompt = f"""中书省方案:
{plan_content}

请审查此方案。从可行性、完备性、风险三个维度分析，给出你的决议。"""
                result = await self._llm.chat([
                    LLMMessage(role='system', content=self.system_prompt),
                    LLMMessage(role='user', content=prompt),
                ])
                review_text = result.content
                review_data = self._extract_json_safe(review_text)
                decision = review_data.get("decision", decision)
                issues = review_data.get("issues", issues)
                suggestions = review_data.get("suggestions", suggestions)
            except Exception:
                pass

        if decision == "approve":
            self.log_event("附议", "方案批准")
            return make_message(
                task_id=msg.task_id,
                speaker=self.speaker,
                msg_type=MessageType.APPROVE,
                content=f"⚖️ 臣门下侍中附议。方案批准。\n\n{review_text}",
                payload={"decision": "approve", "plan": plan_data},
                reply_to=msg.id,
            )
        else:
            self.log_event("封驳", f"驳回: {issues}")
            return make_message(
                task_id=msg.task_id,
                speaker=self.speaker,
                msg_type=MessageType.REJECT,
                content=f"⚖️ 臣门下侍中封驳。方案有如下问题:\n" +
                        "\n".join(f"  - {i}" for i in issues) +
                        f"\n\n修改建议:\n" + "\n".join(f"  - {s}" for s in suggestions),
                payload={
                    "decision": "reject",
                    "issues": issues,
                    "suggestions": suggestions,
                    "plan": plan_data,
                },
                reply_to=msg.id,
            )

    @staticmethod
    def _extract_json_safe(text: str) -> dict:
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
        except Exception:
            pass
        return {}
