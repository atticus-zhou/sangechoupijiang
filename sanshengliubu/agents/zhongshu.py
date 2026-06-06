"""中书省 — 起草方案的自治 Agent

收到用户奏事 → 起草 TaskPlan → 发给门下省审议
收到门下省驳回 → 逐条回应 → 修订方案 → 重新提交
"""

import json
from typing import Optional
from ..llm.providers import LLMMessage

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


ZHONGSHU_PROMPT = """你是中书令，三省六部中的起草官。

## 职责
- 收到用户需求(奏事)后，起草一份可执行的方案(TaskPlan)
- 方案必须拆解为具体步骤，每步指派给正确的部门
- 如果门下省(menxia)驳回方案，你必须逐条回应并修订

## 可指派的部门
- 兵部(bingbu): 代码操作(读/写/搜索/执行命令)
- 刑部(xingbu): 测试/审查/安全扫描
- 吏部(libu): 向量库上下文检索

## 输出格式
回复必须包含一个 JSON 方案:
{
    "title": "方案标题",
    "steps": [
        {"step_id": 1, "assigned_to": "bingbu", "action": "做什么", "detail": "具体指令"}
    ],
    "risk_notes": "风险提示"
}

## 与门下省博弈
- 门下省驳回时会给出具体问题，你必须逐条回应
- 如果对方说得对，修改方案；如果不同意，解释理由
- 最多辩论5轮，超限会升堂请人类裁决"""


class ZhongshuAgent(AutonomousAgent):

    @property
    def speaker(self) -> Speaker:
        return Speaker.ZHONGSHU

    @property
    def system_prompt(self) -> str:
        return ZHONGSHU_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        """自主处理消息"""

        # 吏部分配完成 → 起草方案
        if msg.msg_type == MessageType.ALLOCATION_RESULT:
            return await self._draft_plan(msg)

        # 用户直接奏事 (跳过吏部时) → 起草方案
        if msg.msg_type == MessageType.SUBMIT:
            return await self._draft_plan(msg)

        # 门下省驳回 → 修订方案
        if msg.msg_type == MessageType.REJECT:
            return await self._revise_plan(msg)

        # 需要重新起草 (尚书省否决后)
        if msg.msg_type == MessageType.SYSTEM and "重新起草" in msg.content:
            return await self._draft_plan(msg)

        return None

    async def _draft_plan(self, msg: CourtMessage) -> CourtMessage:
        """起草方案"""
        # 优先使用 payload 中的原始需求，否则用消息正文
        user_request = msg.payload.get("original_request", msg.content)

        content = None
        if self._llm:
            try:
                prompt = f"""用户需求: {user_request}

请起草一份执行方案。输出 JSON。"""
                result = await self._llm.chat([
                    LLMMessage(role='system', content=self.system_prompt),
                    LLMMessage(role='user', content=prompt),
                ])
                content = result.content
                try:
                    plan_data = self._extract_json(content)
                    content = f"臣中书令谨奏方案:\n\n{json.dumps(plan_data, ensure_ascii=False, indent=2)}"
                except Exception:
                    pass
            except Exception:
                pass

        if not content:
            content = f"臣中书令谨奏方案:\n\n{{\n  \"title\": \"{user_request[:30]}...\",\n  \"steps\": [\n    {{\"step_id\": 1, \"assigned_to\": \"bingbu\", \"action\": \"分析问题\"}},\n    {{\"step_id\": 2, \"assigned_to\": \"bingbu\", \"action\": \"实施修改\"}},\n    {{\"step_id\": 3, \"assigned_to\": \"xingbu\", \"action\": \"验证修改\"}}\n  ]\n}}"

        self.log_event("起草", f"起草方案: {user_request[:40]}...")

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.DRAFT_PLAN,
            content=content,
            payload=self._extract_json_safe(content),
            reply_to=msg.id,
        )

    async def _revise_plan(self, msg: CourtMessage) -> CourtMessage:
        """修订方案 — 回应门下省的驳回"""
        reject_reason = msg.content
        original_plan = msg.payload.get("plan", {})

        if self._llm:
            prompt = f"""门下省驳回理由: {reject_reason}

原方案: {json.dumps(original_plan, ensure_ascii=False)}

请修订方案，逐条回应驳回意见。输出 JSON。"""
            result = await self._llm.chat([
                LLMMessage(role='system', content=self.system_prompt),
                LLMMessage(role='user', content=prompt),
            ])
            content = f"臣中书令修订方案:\n\n{result.content}"
        else:
            content = f"臣中书令已根据驳回意见修订方案。（原方案步骤优化）"

        self.log_event("修订", f"回应门下省驳回")

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.DRAFT_PLAN,
            content=content,
            payload=self._extract_json_safe(content),
            reply_to=msg.id,
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从文本中提取 JSON"""
        # 找第一个 { 到最后一个 }
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        return {}

    @staticmethod
    def _extract_json_safe(text: str) -> dict:
        try:
            return ZhongshuAgent._extract_json(text)
        except Exception:
            return {}
