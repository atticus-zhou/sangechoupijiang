"""朝堂事件日志 — 所有动作的不可变日志, 朝堂报告的数据源"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from src.data.schemas import (
    AgentId,
    SystemState,
    CourtEvent,
    CourtReport,
    StateTransition,
)


class CourtEventLog:
    """朝堂事件日志 — 不可变, 追加写"""

    def __init__(self):
        self._events: list[CourtEvent] = []

    def record(
        self,
        task_id: str,
        agent: AgentId,
        state_from: SystemState,
        state_to: SystemState,
        action: str,
        summary: str,
        document_ref: Optional[str] = None,
        detail: dict = None,
    ) -> CourtEvent:
        event = CourtEvent(
            id=str(uuid.uuid4()),
            task_id=task_id,
            timestamp=datetime.now().isoformat(),
            agent=agent,
            state_from=state_from,
            state_to=state_to,
            action=action,
            summary=summary,
            document_ref=document_ref,
            detail=detail or {},
        )
        self._events.append(event)
        return event

    def record_transition(self, task_id: str, transition: StateTransition) -> CourtEvent:
        """从 StateTransition 自动生成 CourtEvent"""
        return self.record(
            task_id=task_id,
            agent=transition.by_agent,
            state_from=transition.from_state,
            state_to=transition.to_state,
            action=f"状态转换: {transition.from_state.value} → {transition.to_state.value}",
            summary=transition.reason,
        )

    # ---- 查询 ----

    def get_recent(self, task_id: str, n: int = 10) -> list[CourtEvent]:
        """获取某任务最近 N 条事件"""
        task_events = [e for e in self._events if e.task_id == task_id]
        return task_events[-n:]

    def get_all(self, task_id: str) -> list[CourtEvent]:
        return [e for e in self._events if e.task_id == task_id]

    def get_unresolved(self, task_id: str) -> list[CourtEvent]:
        """获取未解决的争议事件"""
        return [
            e for e in self._events
            if e.task_id == task_id
            and e.action in ("驳回", "封驳", "否决", "异常")
            and not e.resolved
        ]

    def resolve(self, event_id: str) -> None:
        """标记事件为已解决"""
        for e in self._events:
            if e.id == event_id:
                e.resolved = True
                return

    # ---- 格式化 ----

    def format_recent_activity(self, task_id: str, n: int = 10) -> str:
        """格式化最近活动 — 用于朝堂报告"""
        events = self.get_recent(task_id, n)
        if not events:
            return "（暂无活动记录）"

        lines = []
        for i, e in enumerate(events, 1):
            time = e.timestamp.split("T")[1].split(".")[0] if "T" in e.timestamp else e.timestamp
            lines.append(f"  {i}. [{time}] {e.agent.value} — {e.summary}")
        return "\n".join(lines)

    def format_current_phase(
        self,
        current_state: SystemState,
        round_counters: dict[str, int],
        state_history: list,
    ) -> str:
        """格式化当前阶段信息 — 用于朝堂报告"""
        phase_names = {
            SystemState.RECEIVED: "📥 已接收任务,等待启动",
            SystemState.PLANNING: "📝 中书省起草方案中",
            SystemState.REVIEWING: "⚖️ 门下省审议方案中",
            SystemState.REVISING: "📝 中书省修订方案中 (门下省驳回后)",
            SystemState.APPROVED: "✅ 方案已批准,等待尚书省调度",
            SystemState.DISPATCHING: "🏛️ 尚书省调度决策中",
            SystemState.EXECUTING: "⚔️ 兵部执行中",
            SystemState.TESTING: "🔍 刑部验证中",
            SystemState.ERROR_HANDLING: "⚠️ 异常处理中",
            SystemState.SHANGSHU_VETO: "🛑 尚书省否决",
            SystemState.HUMAN_CALLED: "👤 升堂 — 等待人类裁决",
            SystemState.FINALIZING: "📊 汇总结果中",
            SystemState.DELIVERING: "📬 交付用户中",
            SystemState.COMPLETED: "✅ 任务完成",
            SystemState.TERMINATED: "⛔ 任务终止",
        }

        lines = [
            f"  状态: {phase_names.get(current_state, current_state.value)}",
        ]

        # 循环计数
        for key, val in round_counters.items():
            label = {
                "zhongshu_menxia": "中书-门下讨论轮次",
                "bingbu_xingbu": "兵部-刑部当前步骤重试",
                "orchestrator": "尚书省调度循环",
            }.get(key, key)
            lines.append(f"  {label}: {val}")

        # 总步数
        lines.append(f"  状态转换总步数: {len(state_history)}")

        return "\n".join(lines)

    def format_unresolved_issues(self, task_id: str) -> str:
        """格式化待决议题"""
        unresolved = self.get_unresolved(task_id)
        if not unresolved:
            return "  无待决议题"

        lines = []
        for i, e in enumerate(unresolved, 1):
            lines.append(f"  {i}. [{e.agent.value}] {e.summary}")
            if e.detail:
                for k, v in e.detail.items():
                    lines.append(f"     {k}: {v}")
        return "\n".join(lines)

    def generate_available_actions(self, current_state: SystemState) -> list[str]:
        """根据当前状态生成可用的人类指令"""
        base_actions = ["continue — 继续当前流程", "terminate — 终止任务", "detail <n> — 查看最近第n步详情"]

        state_actions = {
            SystemState.PLANNING: ["reject <意见> — 驳回,让中书省知道你的要求"],
            SystemState.REVIEWING: ["approve — 跳过审议,直接批准", "reject <意见> — 驳回方案"],
            SystemState.REVISING: ["approve — 强制批准当前方案"],
            SystemState.HUMAN_CALLED: [
                "goto planning — 打回中书省重新起草",
                "goto reviewing — 交门下省重新审议",
                "goto dispatching — 直接进入调度阶段",
            ],
            SystemState.ERROR_HANDLING: [
                "retry — 重试当前步骤",
                "skip — 跳过当前步骤",
                "goto planning — 打回中书省重新起草",
            ],
        }

        extra = state_actions.get(current_state, [])
        return base_actions + extra


# 全局单例
court_event_log = CourtEventLog()
