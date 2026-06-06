"""自治 Agent 基类 — 每个 Agent 有自己的事件循环，通过消息总线自主通信

关键设计:
- 每个 Agent 运行自己的 async 循环
- 通过 MessageBus 收发消息，绝不直接调用其他 Agent
- 自主决定何时回应、何时发起新消息
- 可以从外部注入 LLM Provider 和 System Prompt
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator

from .protocols import CourtMessage, Speaker, MessageType, CourtEvent, make_message
from .message_bus import MessageBus


class AutonomousAgent(ABC):
    """自治 Agent 基类

    子类只需实现:
    - speaker: 返回自己的 Speaker 身份
    - system_prompt: 返回系统提示词
    - handle_message: 处理收到的消息，返回回应
    """

    def __init__(self, bus: MessageBus):
        self.bus = bus
        self.bus.register(self.speaker)
        self._active = False
        self._task_id: Optional[str] = None

        # 子类可以设置 LLM provider
        self._llm = None  # BaseLLMProvider

    # ================================================================
    # 子类必须实现
    # ================================================================

    @property
    @abstractmethod
    def speaker(self) -> Speaker:
        """返回此 Agent 的 Speaker 身份"""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """返回此 Agent 的系统提示词"""
        ...

    @abstractmethod
    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        """处理收到的消息，返回回应 (None = 不回应)

        这是 Agent 的核心逻辑。收到消息后:
        1. 判断是否需要回应
        2. 调用 LLM 思考
        3. 返回回应消息 (或 None)
        """
        ...

    # ================================================================
    # 生命周期
    # ================================================================

    async def start(self, task_id: str):
        """启动 Agent 的事件循环"""
        self._active = True
        self._task_id = task_id

    async def stop(self):
        """停止 Agent"""
        self._active = False

    async def run(self):
        """Agent 主循环 — 持续监听消息总线，自主回应"""
        queue = self.bus._queues[self.speaker]
        while self._active:
            # 非阻塞检查队列
            try:
                msg = queue.get_nowait()
            except Exception:
                # 队列空，极短暂休息后重试
                await asyncio.sleep(0.01)
                continue

            if msg.msg_type == MessageType.COMPLETE:
                self._active = False
                break

            try:
                response = await self.handle_message(msg)
                if response:
                    await self.bus.send(response)
            except Exception:
                pass  # 静默处理错误，Agent 继续运行

    # ================================================================
    # 便捷方法
    # ================================================================

    async def say(
        self,
        content: str,
        msg_type: MessageType = MessageType.SYSTEM,
        payload: dict = None,
        reply_to: str = None,
    ) -> CourtMessage:
        """发言 — 创建并发送一条消息"""
        msg = make_message(
            task_id=self._task_id or "",
            speaker=self.speaker,
            msg_type=msg_type,
            content=content,
            payload=payload,
            reply_to=reply_to,
        )
        await self.bus.send(msg)
        return msg

    async def reply_to(self, original: CourtMessage, content: str, msg_type: MessageType = None) -> CourtMessage:
        """回复一条消息"""
        return await self.say(
            content=content,
            msg_type=msg_type or MessageType.RESPONSE,
            reply_to=original.id,
        )

    def set_llm(self, provider):
        """注入 LLM Provider"""
        self._llm = provider

    @property
    def task_id(self) -> str:
        return self._task_id or ""

    def log_event(self, action: str, summary: str) -> None:
        """记录朝堂事件"""
        self.bus.log_event(CourtEvent(
            task_id=self._task_id or "",
            speaker=self.speaker,
            action=action,
            summary=summary,
        ))
