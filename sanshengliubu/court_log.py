"""朝堂日志 — 事件记录与朝堂报告生成"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .protocols import CourtMessage, CourtEvent, Speaker


class CourtReporter:
    """朝堂报告生成器 — 从消息日志和事件日志中生成报告"""

    def __init__(self):
        self._messages: list[CourtMessage] = []
        self._events: list[CourEvent] = []

    def record_message(self, msg: CourtMessage) -> None:
        self._messages.append(msg)

    def record_event(self, event: CourtEvent) -> None:
        self._events.append(event)

    def get_task_messages(self, task_id: str) -> list[CourtMessage]:
        return [m for m in self._messages if m.task_id == task_id]

    def get_task_events(self, task_id: str) -> list[CourEvent]:
        return [e for e in self._events if e.task_id == task_id]

    def generate_report(self, task_id: str) -> str:
        """生成朝堂报告"""
        msgs = self.get_task_messages(task_id)
        events = self.get_task_events(task_id)

        if not msgs:
            return "(无活动记录)"

        lines = [
            "═" * 55,
            "          🏛️  朝 堂 报 告",
            f"         任务: {task_id}",
            f"         时间: {datetime.now().isoformat()[:19]}",
            "═" * 55,
            "",
            "【消息记录】",
        ]

        for msg in msgs[-20:]:  # 最近 20 条
            speaker = msg.speaker.emoji + " " + msg.speaker.display_name
            content_preview = msg.content[:120] + ("..." if len(msg.content) > 120 else "")
            lines.append(f"  {speaker}: {content_preview}")

        if events:
            lines.append("")
            lines.append("【关键事件】")
            for evt in events[-10:]:
                lines.append(f"  [{evt.speaker.display_name}] {evt.action}: {evt.summary}")

        lines.append("")
        lines.append("═" * 55)

        return "\n".join(lines)

    def get_latest_plan(self, task_id: str) -> Optional[dict]:
        """获取最新的方案内容"""
        for msg in reversed(self._messages):
            if msg.task_id == task_id and msg.speaker == Speaker.ZHONGSHU:
                if msg.payload and "steps" in msg.payload:
                    return msg.payload
        return None

    def get_latest_review(self, task_id: str) -> Optional[dict]:
        """获取最新的审议结果"""
        for msg in reversed(self._messages):
            if msg.task_id == task_id and msg.speaker == Speaker.MENXIA:
                if msg.payload and "decision" in msg.payload:
                    return msg.payload
        return None

    def get_current_phase(self, task_id: str) -> str:
        """判断当前处于什么阶段"""
        msgs = self.get_task_messages(task_id)
        if not msgs:
            return "未开始"

        last_msg = msgs[-1]

        # 检查是否有尚书省在调度
        for msg in reversed(msgs):
            if msg.speaker == Speaker.SHANGSHU:
                if msg.msg_type.value == "dispatch":
                    return "执行阶段 (尚书省调度中)"
                elif msg.msg_type.value == "complete":
                    return "已完成"

        # 检查门下省
        for msg in reversed(msgs):
            if msg.speaker == Speaker.MENXIA:
                if msg.msg_type.value == "reject":
                    return "方案阶段 (门下省驳回,等待中书省修订)"
                elif msg.msg_type.value == "approve":
                    return "方案阶段 (门下省批准,等待尚书省调度)"

        # 默认
        if last_msg.speaker == Speaker.ZHONGSHU:
            return "方案阶段 (中书省起草中)"
        elif last_msg.speaker == Speaker.MENXIA:
            return "方案阶段 (门下省审议中)"

        return "进行中"


court_reporter = CourtReporter()
