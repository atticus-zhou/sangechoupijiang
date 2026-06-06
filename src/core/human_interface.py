"""人类介入接口 — 处理打断、呈现报告、接收指令"""

from __future__ import annotations

import asyncio
from typing import Optional

from src.data.schemas import (
    SystemState,
    HumanCommand,
    HumanInstruction,
    CourtReport,
)
from src.core.state_machine import StateMachine
from src.core.court_report import court_report_generator


class HumanInterface:
    """人类介入管理器"""

    def __init__(self):
        self._interrupt_requested: bool = False
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # 初始为非暂停状态
        self._on_report: Optional[callable] = None  # 报告输出回调

    # ---- 打断 ----

    def request_interrupt(self) -> None:
        """请求打断当前流程"""
        self._interrupt_requested = True

    def is_interrupted(self) -> bool:
        return self._interrupt_requested

    async def wait_if_paused(self) -> None:
        """如果被打断，等待人类指令后恢复"""
        if self._interrupt_requested:
            await self._pause_event.wait()

    def clear_interrupt(self) -> None:
        self._interrupt_requested = False
        self._pause_event.set()

    def set_report_callback(self, callback: callable) -> None:
        """设置报告输出回调 (如 print 到控制台)"""
        self._on_report = callback

    # ---- 自动暂停节点 ----

    def should_auto_pause(self, state: StateMachine, config) -> bool:
        """检查是否应该自动暂停等待人类"""
        # 中书-门下达到上限
        if state.is_max_rounds_exceeded("zhongshu_menxia", config.zhongshu_menxia_max_rounds):
            return True

        # 兵部-刑部达到上限
        if state.is_max_rounds_exceeded("bingbu_xingbu", config.bingbu_xingbu_max_retries):
            return True

        # 尚书省否决指向人类
        if state.current_state == SystemState.SHANGSHU_VETO:
            return True

        return False

    # ---- 交互流程 ----

    async def handle_interrupt(
        self,
        task_id: str,
        state: StateMachine,
    ) -> HumanInstruction:
        """
        处理打断: 生成并输出朝堂报告, 等待人类指令
        返回 HumanInstruction
        """
        # 生成报告
        report = await court_report_generator.generate(task_id, state)
        formatted = court_report_generator.format_report(report)

        # 输出报告
        if self._on_report:
            self._on_report(formatted)
        else:
            print(formatted)

        # 等待人类输入
        # 在实际 CLI 中这里会是一个 input() 调用
        # 在程序化场景中，通过 receive_command() 注入
        pass

    async def receive_command(self, text: str) -> HumanInstruction:
        """接收人类指令文本，解析并返回"""
        cmd = court_report_generator.parse_human_command(text)
        self.clear_interrupt()
        return cmd

    async def present_and_wait(
        self,
        task_id: str,
        state: StateMachine,
        get_input: callable = None,
    ) -> HumanInstruction:
        """呈现报告并等待人类输入 (阻塞)"""
        report = await court_report_generator.generate(task_id, state)
        formatted = court_report_generator.format_report(report)

        if self._on_report:
            self._on_report(formatted)

        if get_input:
            text = await get_input(formatted)
        else:
            # 使用 asyncio.to_thread 避免阻塞事件循环
            text = await asyncio.to_thread(input, "\n> ")

        return court_report_generator.parse_human_command(text)


# 全局单例
human_interface = HumanInterface()
