"""
三省六部 · 多 Agent 协作框架

一个基于中国古代三省六部制度的自治多 Agent 协作 SDK。

六部职能:
    🎯 吏部 — 分配子Agent, 分析任务后决定调动哪些部门
    💰 户部 — 资源/数据管理, Token预算, API调用
    📡 礼部 — 通信/外交, 格式化输出, 多平台适配
    ⚔️ 兵部 — 执行/行动, 写代码, 跑命令
    🔍 刑部 — 验证/测试, 代码审查, 安全检查
    🖼️ 工部 — 构建/图片生成, 数据图表, 架构图, 宣传图

用法:
    from sanshengliubu import CourtSession

    async with CourtSession(config) as court:
        async for event in court.submit("修复订单超时"):
            print(f"[{event.speaker.label}] {event.content}")
"""

from .session import CourtSession
from .agent import AutonomousAgent
from .protocols import (
    CourtMessage,
    Speaker,
    MessageType,
    TaskPlan,
    ReviewResult,
    StepResult,
)

__all__ = [
    "CourtSession",
    "AutonomousAgent",
    "CourtMessage",
    "Speaker",
    "MessageType",
    "TaskPlan",
    "ReviewResult",
    "StepResult",
]
