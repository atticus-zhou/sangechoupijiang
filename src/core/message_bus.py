"""消息总线 — Agent 间消息路由和记录"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
    MessageMetadata,
    VectorDocument,
    VectorMetadata,
)


class MessageBus:
    """Agent 间消息路由中心"""

    def __init__(self):
        self._subscribers: dict[AgentId, asyncio.Queue[AgentMessage]] = {}
        self._message_log: list[AgentMessage] = []
        self._on_store: Optional[callable] = None  # 吏部存储回调

    # ---- 注册 ----

    def register(self, agent: AgentId) -> None:
        if agent not in self._subscribers:
            self._subscribers[agent] = asyncio.Queue()

    def unregister(self, agent: AgentId) -> None:
        self._subscribers.pop(agent, None)

    def set_store_callback(self, callback: callable) -> None:
        """设置存储回调 — 吏部在注册时调用此方法"""
        self._on_store = callback

    # ---- 发送 ----

    async def send(self, msg: AgentMessage) -> None:
        """发送消息到目标 agent 的队列，并写入日志"""
        self._message_log.append(msg)

        # 如果有吏部存储回调，写入向量库
        if self._on_store:
            try:
                vec_doc = self._msg_to_vector_doc(msg)
                await self._on_store(vec_doc)
            except Exception:
                pass  # 存储失败不影响消息投递

        # 投递到目标队列
        if msg.to_agent in self._subscribers:
            await self._subscribers[msg.to_agent].put(msg)

    async def broadcast(self, msg: AgentMessage) -> None:
        """广播消息给所有已注册 agent"""
        for agent in list(self._subscribers.keys()):
            broadcast_msg = AgentMessage(
                id=str(uuid.uuid4()),
                task_id=msg.task_id,
                from_agent=msg.from_agent,
                to_agent=agent,
                msg_type=msg.msg_type,
                payload=msg.payload,
                context_refs=msg.context_refs,
                parent_msg_id=msg.id,
                metadata=MessageMetadata(
                    tokens_used=msg.metadata.tokens_used,
                    timestamp=datetime.now().isoformat(),
                ),
            )
            await self.send(broadcast_msg)

    # ---- 接收 ----

    async def receive(self, agent: AgentId, timeout: float = None) -> AgentMessage:
        """阻塞等待接收消息"""
        if agent not in self._subscribers:
            self.register(agent)
        try:
            return await asyncio.wait_for(
                self._subscribers[agent].get(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"{agent.value} 等待消息超时 ({timeout}s)")

    async def receive_nowait(self, agent: AgentId) -> Optional[AgentMessage]:
        """非阻塞获取消息"""
        if agent not in self._subscribers:
            return None
        queue = self._subscribers[agent]
        if queue.empty():
            return None
        return queue.get_nowait()

    # ---- 查询 ----

    def get_recent_messages(self, task_id: str, n: int = 20) -> list[AgentMessage]:
        """获取某任务的最近 N 条消息"""
        return [m for m in self._message_log if m.task_id == task_id][-n:]

    def get_task_messages(self, task_id: str) -> list[AgentMessage]:
        """获取某任务的全部消息"""
        return [m for m in self._message_log if m.task_id == task_id]

    def get_last_message(self, task_id: str, from_agent: AgentId = None) -> Optional[AgentMessage]:
        """获取某任务最近一条消息，可按发送者过滤"""
        msgs = self.get_task_messages(task_id)
        if from_agent:
            msgs = [m for m in msgs if m.from_agent == from_agent]
        return msgs[-1] if msgs else None

    # ---- 辅助 ----

    @staticmethod
    def _msg_to_vector_doc(msg: AgentMessage) -> VectorDocument:
        return VectorDocument(
            id=msg.id,
            content=f"[{msg.from_agent.value} → {msg.to_agent.value}] {msg.msg_type.value}\n{msg.payload}",
            metadata=VectorMetadata(
                doc_type="agent_message",
                task_id=msg.task_id,
                agent=msg.from_agent,
                timestamp=msg.metadata.timestamp,
                tags=[msg.msg_type.value],
            ),
        )

    @staticmethod
    def create_message(
        task_id: str,
        from_agent: AgentId,
        to_agent: AgentId,
        msg_type: MessageType,
        payload: dict = None,
        context_refs: list[str] = None,
        parent_msg_id: str = None,
        confidence: float = 1.0,
    ) -> AgentMessage:
        return AgentMessage(
            id=str(uuid.uuid4()),
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            msg_type=msg_type,
            payload=payload or {},
            context_refs=context_refs or [],
            parent_msg_id=parent_msg_id,
            metadata=MessageMetadata(confidence=confidence),
        )


# 全局单例
message_bus = MessageBus()
