"""状态机引擎 — 管理系统状态转换合法性、循环计数"""

from __future__ import annotations

from datetime import datetime
from src.data.schemas import (
    SystemState,
    StateTransition,
    AgentId,
)


class IllegalTransitionError(Exception):
    """非法状态转换"""
    pass


# 合法状态转换表
_TRANSITIONS: dict[SystemState, list[SystemState]] = {
    SystemState.RECEIVED:       [SystemState.PLANNING, SystemState.TERMINATED],
    SystemState.PLANNING:       [SystemState.REVIEWING, SystemState.APPROVED, SystemState.HUMAN_CALLED, SystemState.TERMINATED],
    SystemState.REVIEWING:      [SystemState.APPROVED, SystemState.REVISING, SystemState.HUMAN_CALLED, SystemState.TERMINATED],
    SystemState.REVISING:       [SystemState.REVIEWING, SystemState.APPROVED, SystemState.HUMAN_CALLED, SystemState.TERMINATED],
    SystemState.APPROVED:       [SystemState.DISPATCHING, SystemState.TERMINATED],
    SystemState.DISPATCHING:    [
        SystemState.EXECUTING, SystemState.TESTING, SystemState.ERROR_HANDLING,
        SystemState.FINALIZING, SystemState.SHANGSHU_VETO, SystemState.HUMAN_CALLED,
        SystemState.PLANNING, SystemState.TERMINATED,
    ],
    SystemState.EXECUTING:      [SystemState.TESTING, SystemState.DISPATCHING, SystemState.ERROR_HANDLING, SystemState.TERMINATED],
    SystemState.TESTING:        [SystemState.DISPATCHING, SystemState.EXECUTING, SystemState.ERROR_HANDLING, SystemState.TERMINATED],
    SystemState.ERROR_HANDLING: [SystemState.DISPATCHING, SystemState.SHANGSHU_VETO, SystemState.HUMAN_CALLED, SystemState.TERMINATED],
    SystemState.SHANGSHU_VETO:  [SystemState.PLANNING, SystemState.HUMAN_CALLED, SystemState.TERMINATED],
    SystemState.HUMAN_CALLED:   [
        SystemState.PLANNING, SystemState.REVIEWING, SystemState.DISPATCHING,
        SystemState.EXECUTING, SystemState.TESTING, SystemState.TERMINATED,
    ],
    SystemState.FINALIZING:     [SystemState.DELIVERING, SystemState.TERMINATED],
    SystemState.DELIVERING:     [SystemState.COMPLETED, SystemState.TERMINATED],
    SystemState.COMPLETED:      [],
    SystemState.TERMINATED:     [],
}


class StateMachine:
    """手写状态机"""

    def __init__(self):
        self.current_state: SystemState = SystemState.RECEIVED
        self.state_history: list[StateTransition] = []
        self._round_counters: dict[str, int] = {}  # 各类循环计数

    # ---- 状态查询 ----

    def can_transition(self, target: SystemState) -> bool:
        return target in _TRANSITIONS.get(self.current_state, [])

    def allowed_targets(self) -> list[SystemState]:
        return _TRANSITIONS.get(self.current_state, [])

    # ---- 状态转换 ----

    def transition(self, target: SystemState, reason: str, by_agent: AgentId) -> StateTransition:
        # 自循环: 不报错, 记录但不改变状态
        if target == self.current_state:
            return None
        if not self.can_transition(target):
            raise IllegalTransitionError(
                f"非法状态转换: {self.current_state.value} → {target.value}"
            )
        t = StateTransition(
            from_state=self.current_state,
            to_state=target,
            reason=reason,
            by_agent=by_agent,
            timestamp=datetime.now().isoformat(),
        )
        self.state_history.append(t)
        self.current_state = target
        return t

    def force_transition(self, target: SystemState, reason: str) -> StateTransition:
        """人类强制跳转 — 跳过合法性检查"""
        t = StateTransition(
            from_state=self.current_state,
            to_state=target,
            reason=f"[人类强制] {reason}",
            by_agent=AgentId.HUMAN,
            timestamp=datetime.now().isoformat(),
        )
        self.state_history.append(t)
        self.current_state = target
        return t

    # ---- 循环计数 ----

    def increment_round(self, round_type: str) -> int:
        """增加指定类型的循环计数, 返回当前值"""
        self._round_counters[round_type] = self._round_counters.get(round_type, 0) + 1
        return self._round_counters[round_type]

    def get_round(self, round_type: str) -> int:
        return self._round_counters.get(round_type, 0)

    def reset_round(self, round_type: str) -> None:
        self._round_counters[round_type] = 0

    def is_max_rounds_exceeded(self, round_type: str, max_rounds: int) -> bool:
        return self._round_counters.get(round_type, 0) >= max_rounds

    def reset_all_rounds(self) -> None:
        self._round_counters.clear()

    # ---- 便捷方法 ----

    def is_terminal(self) -> bool:
        return self.current_state in (SystemState.COMPLETED, SystemState.TERMINATED)

    def is_planning_phase(self) -> bool:
        """是否处于方案阶段 (中书-门下讨论)"""
        return self.current_state in (
            SystemState.RECEIVED, SystemState.PLANNING,
            SystemState.REVIEWING, SystemState.REVISING,
        )

    def is_execution_phase(self) -> bool:
        """是否处于执行阶段"""
        return self.current_state in (
            SystemState.APPROVED, SystemState.DISPATCHING,
            SystemState.EXECUTING, SystemState.TESTING,
            SystemState.ERROR_HANDLING,
        )

    def summary(self) -> str:
        """人类可读的状态摘要"""
        rounds_str = ", ".join(f"{k}={v}" for k, v in self._round_counters.items())
        steps_count = len(self.state_history)
        last = self.state_history[-1] if self.state_history else None
        last_info = f", 上一步: {last.from_state.value}→{last.to_state.value} ({last.by_agent.value})" if last else ""
        return (
            f"当前状态: {self.current_state.value}"
            f", 总步数: {steps_count}"
            f", 循环计数: [{rounds_str}]"
            f"{last_info}"
        )
