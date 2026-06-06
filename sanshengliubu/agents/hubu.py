"""户部 — 💰 资源/数据管理

户部管理朝堂的"钱粮"——在现代语境下即 Token 预算、API 调用、外部数据获取。

职能:
- 管理 Token 预算 (这个任务花多少 token)
- 获取外部数据 (API 调用、数据库查询)
- 消耗统计和成本报告
- 文件/数据读写操作
"""

from typing import Optional

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


HUBU_PROMPT = """你是户部尚书，三省六部中的财政和资源管理者。

## 职责
- 管理 Token 预算: 每步操作消耗多少，是否超出预算
- 获取外部数据: API调用、数据库查询、文件读取
- 成本报告: 任务完成后的资源消耗统计

## 你管理的资源
- Token (调用 LLM 的消耗)
- API 配额
- 外部数据源

## 输出格式
{
    "action": "fetch_data | token_report",
    "data": {},
    "budget": {"used": 0, "total": 0, "remaining": 0}
}"""


class HubuAgent(AutonomousAgent):

    def __init__(self, bus):
        super().__init__(bus)
        self._token_used = 0
        self._token_budget = 100000  # 默认预算
        self._api_calls = 0

    @property
    def speaker(self) -> Speaker:
        return Speaker.HUBU

    @property
    def system_prompt(self) -> str:
        return HUBU_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        if msg.msg_type == MessageType.FETCH_DATA:
            return await self._fetch_data(msg)

        if msg.msg_type == MessageType.QUERY:
            return await self._report_budget(msg)

        return None

    async def _fetch_data(self, msg: CourtMessage) -> CourtMessage:
        """获取外部数据"""
        query = msg.payload.get("query", "")
        self.log_event("获取数据", f"查询: {query[:50]}...")

        # TBD: 实际的外部数据获取
        self._api_calls += 1
        self._token_used += 500  # 模拟消耗

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.DATA_READY,
            content=f"💰 户部已获取数据。(查询: {query[:50]}...)",
            payload={"data": {}, "query": query},
            reply_to=msg.id,
        )

    async def _report_budget(self, msg: CourtMessage) -> CourtMessage:
        """报告预算使用情况"""
        remaining = self._token_budget - self._token_used
        percentage = (self._token_used / self._token_budget * 100) if self._token_budget > 0 else 0

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.TOKEN_REPORT,
            content=f"💰 预算报告: 已用 {self._token_used}/{self._token_budget} tokens ({percentage:.1f}%) | API调用 {self._api_calls}次",
            payload={
                "used": self._token_used,
                "total": self._token_budget,
                "remaining": remaining,
                "api_calls": self._api_calls,
            },
            reply_to=msg.id,
        )
