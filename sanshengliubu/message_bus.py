"""消息总线 — Agent 间通信的唯一通道

每个 Agent 通过总线发送和接收消息，禁止直接调用其他 Agent 的方法。
消息总线同时负责:
- 消息路由 (发到正确的 Agent)
- 消息广播 (所有 Agent 可见)
- 消息日志 (用于朝堂报告回溯)
- 异步流式输出 (外部订阅者可见每个消息)
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional, Callable, Awaitable

from .protocols import CourtMessage, Speaker, CourtEvent


class MessageBus:
    """Agent 间消息路由中心"""

    def __init__(self):
        # 每个 Speaker 一个消息队列
        self._queues: dict[Speaker, asyncio.Queue[CourtMessage]] = {}

        # 全局消息日志
        self._log: list[CourtMessage] = []

        # 事件日志 (用于朝堂报告)
        self._events: list[CourEvent] = []

        # 外部订阅者 — 每个新消息都会推送给订阅者
        self._subscribers: list[Callable[[CourtMessage], Awaitable[None]]] = []

        # 广播通道 — 所有 Agent 都能收到的消息
        self._broadcast_subscribers: list[Callable[[CourtMessage], Awaitable[None]]] = []

    # ================================================================
    # 注册
    # ================================================================

    def register(self, speaker: Speaker) -> None:
        """注册一个 Agent 到总线"""
        if speaker not in self._queues:
            self._queues[speaker] = asyncio.Queue()

    def subscribe(self, callback: Callable[[CourtMessage], Awaitable[None]]) -> None:
        """外部订阅者 — 每个消息都会被推送"""
        self._subscribers.append(callback)

    def on_broadcast(self, callback: Callable[[CourtMessage], Awaitable[None]]) -> None:
        """订阅广播消息"""
        self._broadcast_subscribers.append(callback)

    # ================================================================
    # 发送
    # ================================================================

    async def send(self, msg: CourtMessage) -> None:
        """发送消息到目标 Speaker 的队列"""
        self._log.append(msg)

        # 如果目标是特定 speaker，放入其队列
        target = msg.msg_type  # 由协议决定路由逻辑
        # 实际路由：基于 msg 的语义目标
        resolved_target = self._resolve_target(msg)
        if resolved_target:
            if resolved_target not in self._queues:
                self.register(resolved_target)
            await self._queues[resolved_target].put(msg)

        # 通知外部订阅者
        for sub in self._subscribers:
            try:
                await sub(msg)
            except Exception:
                pass

    async def broadcast(self, msg: CourtMessage) -> None:
        """广播消息给所有 Agent"""
        self._log.append(msg)
        for speaker, queue in self._queues.items():
            if speaker != msg.speaker:  # 不发给自己
                await queue.put(msg)

        for sub in self._broadcast_subscribers:
            try:
                await sub(msg)
            except Exception:
                pass

        for sub in self._subscribers:
            try:
                await sub(msg)
            except Exception:
                pass

    async def send_to(self, target: Speaker, msg: CourtMessage) -> None:
        """直接发送给指定 Agent"""
        self._log.append(msg)
        await self._queues[target].put(msg)

        for sub in self._subscribers:
            try:
                await sub(msg)
            except Exception:
                pass

    # ================================================================
    # 接收
    # ================================================================

    async def receive(self, speaker: Speaker, timeout: float = None) -> CourtMessage:
        """阻塞等待接收发给该 Speaker 的消息"""
        queue = self._queues[speaker]
        try:
            if timeout:
                return await asyncio.wait_for(queue.get(), timeout=timeout)
            return await queue.get()
        except asyncio.TimeoutError:
            raise TimeoutError(f"{speaker.value} 等待消息超时")

    async def receive_nowait(self, speaker: Speaker) -> Optional[CourtMessage]:
        """非阻塞获取消息"""
        queue = self._queues[speaker]
        if queue.empty():
            return None
        return queue.get_nowait()

    # ================================================================
    # 日志与事件
    # ================================================================

    def log_event(self, event: CourtEvent) -> None:
        self._events.append(event)

    def get_messages(self, task_id: str) -> list[CourtMessage]:
        """获取某任务的全部消息"""
        return [m for m in self._log if m.task_id == task_id]

    def get_events(self, task_id: str) -> list[CourEvent]:
        """获取某任务的全部事件"""
        return [e for e in self._events if e.task_id == task_id]

    def get_recent_messages(self, task_id: str, n: int = 10) -> list[CourtMessage]:
        return self.get_messages(task_id)[-n:]

    # ================================================================
    # 流式输出 — 外部可以 async for 遍历消息
    # ================================================================

    async def stream(self, task_id: str) -> AsyncIterator[CourtMessage]:
        """异步迭代器 — 产出某任务的实时消息流"""
        seen = len(self.get_messages(task_id))
        # 先吐出已有消息
        for msg in self.get_messages(task_id):
            yield msg

        # 再监听新消息
        queue: asyncio.Queue[CourtMessage] = asyncio.Queue()

        async def on_msg(msg: CourtMessage):
            if msg.task_id == task_id:
                await queue.put(msg)

        self._subscribers.append(on_msg)
        try:
            while True:
                msg = await queue.get()
                yield msg
        except asyncio.CancelledError:
            pass
        finally:
            self._subscribers.remove(on_msg)

    # ================================================================
    # 内部
    # ================================================================

    def _resolve_target(self, msg: CourtMessage) -> Optional[Speaker]:
        """根据消息类型解析目标 Speaker — 显式 target 优先"""
        # 1. 显式指定了接收者
        if msg.target:
            return msg.target

        # 2. 路由表 (基于 speaker + msg_type)
        routing = {
            # 中书↔门下
            (Speaker.ZHONGSHU, "draft_plan"): Speaker.MENXIA,
            (Speaker.MENXIA, "reject"): Speaker.ZHONGSHU,
            (Speaker.MENXIA, "approve"): Speaker.SHANGSHU,
            # 尚书省调度
            (Speaker.SHANGSHU, "dispatch"): Speaker.BINGBU,
            (Speaker.SHANGSHU, "verify"): Speaker.XINGBU,
            (Speaker.SHANGSHU, "fetch_data"): Speaker.HUBU,
            (Speaker.SHANGSHU, "format_output"): Speaker.LIBU_COMM,
            (Speaker.SHANGSHU, "generate_image"): Speaker.GONGBU,
            (Speaker.SHANGSHU, "build"): Speaker.GONGBU,
            # 用户提交 → 先到吏部分配
            (Speaker.USER, "submit"): Speaker.LIBU,
            # 六部 → 尚书省
            (Speaker.BINGBU, "result"): Speaker.SHANGSHU,
            (Speaker.XINGBU, "verdict"): Speaker.SHANGSHU,
            (Speaker.HUBU, "data_ready"): Speaker.SHANGSHU,
            (Speaker.HUBU, "token_report"): Speaker.SHANGSHU,
            (Speaker.LIBU_COMM, "output_ready"): Speaker.SHANGSHU,
            (Speaker.GONGBU, "image_ready"): Speaker.SHANGSHU,
            (Speaker.GONGBU, "result"): Speaker.SHANGSHU,
            (Speaker.LIBU, "response"): Speaker.SHANGSHU,
            (Speaker.LIBU, "allocation_result"): Speaker.ZHONGSHU,
        }
        return routing.get((msg.speaker, msg.msg_type.value))
