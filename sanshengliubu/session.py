"""CourtSession — 朝堂会话管理

轻量级会话管理器：
- 创建 Agent 实例并连接到消息总线
- 提交任务 (奏事)
- 流式输出事件 (外部可 async for)
- 不是单体调度器 — Agent 之间的协作是自治的
"""

from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator, Optional

from .protocols import (
    CourtMessage,
    CourtEvent,
    Speaker,
    MessageType,
    make_message,
    format_agent_message,
)
from .message_bus import MessageBus
from .agent import AutonomousAgent
from .config.loader import CourtConfig, AgentConfig
from .llm.providers import LLMFactory, ModelConfig
from .court_log import court_reporter


class CourtSession:
    """朝堂会话 — 创建一场三省六部会议"""

    def __init__(self, config: CourtConfig = None, config_dict: dict = None):
        """
        参数:
            config: CourtConfig 对象
            config_dict: 字典格式的配置 (可替代 config)
        """
        if config_dict:
            self.config = CourtConfig.from_dict(config_dict)
        elif config:
            self.config = config
        else:
            self.config = CourtConfig()

        self.bus = MessageBus()
        self._agents: dict[Speaker, AutonomousAgent] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._task_id: Optional[str] = None

    # ================================================================
    # Agent 管理
    # ================================================================

    def register_agent(self, agent: AutonomousAgent) -> None:
        """注册一个自定义 Agent (用户可注入)"""
        self._agents[agent.speaker] = agent

    def _ensure_default_agents(self) -> None:
        """确保三省六部的默认 Agent 已注册"""
        from .agents.zhongshu import ZhongshuAgent
        from .agents.menxia import MenxiaAgent
        from .agents.shangshu import ShangshuAgent
        from .agents.bingbu import BingbuAgent
        from .agents.xingbu import XingbuAgent
        from .agents.libu import LibuAgent
        from .agents.hubu import HubuAgent
        from .agents.libu_comm import LibuCommAgent
        from .agents.gongbu import GongbuAgent

        defaults = {
            Speaker.ZHONGSHU: ZhongshuAgent,
            Speaker.MENXIA: MenxiaAgent,
            Speaker.SHANGSHU: ShangshuAgent,
            Speaker.LIBU: LibuAgent,
            Speaker.HUBU: HubuAgent,
            Speaker.LIBU_COMM: LibuCommAgent,
            Speaker.BINGBU: BingbuAgent,
            Speaker.XINGBU: XingbuAgent,
            Speaker.GONGBU: GongbuAgent,
        }

        for speaker, agent_cls in defaults.items():
            if speaker not in self._agents:
                agent = agent_cls(self.bus)
                # 注入 LLM provider
                ac = self.config.get_agent_config(speaker.value)
                mc = ModelConfig(
                    provider=ac.provider,
                    model=ac.model,
                    api_key=ac.api_key,
                    api_base=ac.api_base,
                    temperature=ac.temperature,
                    max_tokens=ac.max_tokens,
                )
                agent.set_llm(LLMFactory.create(mc))
                self._agents[speaker] = agent

    # ================================================================
    # 提交任务 (奏事)
    # ================================================================

    async def submit(self, user_request: str) -> AsyncIterator[CourtMessage]:
        """提交任务并流式返回消息

        用法:
            async for msg in court.submit("修复订单超时"):
                print(format_agent_message(msg))
        """
        task_id = str(uuid.uuid4())[:8]
        self._task_id = task_id
        self._ensure_default_agents()

        # 创建一个队列用于流式输出
        output_queue: asyncio.Queue[CourtMessage] = asyncio.Queue()

        async def on_message(msg: CourtMessage):
            if msg.task_id == task_id:
                court_reporter.record_message(msg)
                await output_queue.put(msg)

        self.bus.subscribe(on_message)

        # 启动所有 Agent
        agent_tasks = []
        for agent in self._agents.values():
            await agent.start(task_id)
            task = asyncio.create_task(agent.run())
            agent_tasks.append(task)
            self._tasks[agent.speaker.value] = task

        try:
            # 发送用户奏事
            user_msg = make_message(
                task_id=task_id,
                speaker=Speaker.USER,
                msg_type=MessageType.SUBMIT,
                content=user_request,
            )
            await self.bus.send(user_msg)

            # 流式输出消息，直到收到 COMPLETE 或超时
            while True:
                try:
                    msg = await asyncio.wait_for(output_queue.get(), timeout=300.0)
                    yield msg
                    if msg.msg_type == MessageType.COMPLETE:
                        break
                except asyncio.TimeoutError:
                    break

        finally:
            # 停止所有 Agent
            for agent in self._agents.values():
                await agent.stop()

            for task in agent_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def submit_and_collect(self, user_request: str) -> list[CourtMessage]:
        """提交任务并收集所有消息 (非流式)"""
        messages = []
        async for msg in self.submit(user_request):
            messages.append(msg)
        return messages

    # ================================================================
    # 朝堂报告
    # ================================================================

    def get_report(self) -> str:
        """获取当前任务的朝堂报告"""
        if not self._task_id:
            return "(无进行中的任务)"
        return court_reporter.generate_report(self._task_id)

    def get_current_phase(self) -> str:
        if not self._task_id:
            return "未开始"
        return court_reporter.get_current_phase(self._task_id)

    def get_latest_plan(self) -> Optional[dict]:
        if not self._task_id:
            return None
        return court_reporter.get_latest_plan(self._task_id)

    def get_messages(self) -> list[CourtMessage]:
        if not self._task_id:
            return []
        return court_reporter.get_task_messages(self._task_id)

    # ================================================================
    # 上下文管理
    # ================================================================

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        for agent in self._agents.values():
            await agent.stop()
        self._agents.clear()
        self._tasks.clear()
