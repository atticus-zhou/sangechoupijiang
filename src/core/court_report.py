"""朝堂报告生成器 — 综合事件日志、状态机、向量库数据生成完整报告"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Callable

from src.data.schemas import (
    CourtReport,
    SystemState,
    HumanCommand,
    HumanInstruction,
)
from src.core.state_machine import StateMachine
from src.core.court_event_log import court_event_log


class CourtReportGenerator:
    """朝堂报告生成器"""

    def __init__(self, get_latest_docs: Optional[Callable] = None):
        """
        get_latest_docs: 异步回调, 参数 (task_id: str) → list[dict]
                        用于从吏部获取最新文件全文
        """
        self._get_latest_docs = get_latest_docs

    def set_doc_fetcher(self, fetcher: Callable) -> None:
        self._get_latest_docs = fetcher

    async def generate(self, task_id: str, state: StateMachine) -> CourtReport:
        """生成完整朝堂报告"""

        # 1. 上一流程做了什么
        recent_activity = court_event_log.format_recent_activity(task_id, n=10)

        # 2. 当前阶段
        current_phase = court_event_log.format_current_phase(
            state.current_state,
            state._round_counters,
            state.state_history,
        )

        # 3. 最新文件 (全文)
        latest_docs = []
        if self._get_latest_docs:
            try:
                latest_docs = await self._get_latest_docs(task_id)
            except Exception:
                latest_docs = [{"error": "无法获取最新文件"}]

        # 4. 待决议题
        unresolved_text = court_event_log.format_unresolved_issues(task_id)
        unresolved_issues = [
            {"summary": e.summary, "detail": e.detail, "agent": e.agent.value}
            for e in court_event_log.get_unresolved(task_id)
        ]

        # 5. 可用指令
        available_actions = court_event_log.generate_available_actions(state.current_state)

        return CourtReport(
            task_id=task_id,
            generated_at=datetime.now().isoformat(),
            recent_activity=recent_activity,
            current_phase=current_phase,
            latest_documents=latest_docs,
            unresolved_issues=unresolved_issues,
            available_actions=available_actions,
        )

    @staticmethod
    def format_report(report: CourtReport) -> str:
        """将 CourtReport 格式化为终端可读的字符串"""
        lines = [
            "═" * 65,
            "                   🏛️  朝 堂 报 告",
            f"                   任务: {report.task_id}",
            f"                   时间: {report.generated_at}",
            "═" * 65,
            "",
            "【上一流程做了什么】",
            report.recent_activity,
            "",
            "【当前阶段】",
            report.current_phase,
            "",
        ]

        # 最新文件
        if report.latest_documents:
            lines.append("【最新文件 — 全文输出】")
            for i, doc in enumerate(report.latest_documents, 1):
                lines.append(f"  ┌─ 文件 {i}: {doc.get('doc_type', '未知')} ─")
                lines.append(f"  │ 状态: {doc.get('status', '未知')}")
                lines.append(f"  │ 版本: v{doc.get('version', '?')}")
                content = doc.get("content", "")
                for content_line in content.split("\n")[:30]:  # 最多30行
                    lines.append(f"  │ {content_line}")
                lines.append("  └" + "─" * 40)
            lines.append("")

        # 待决议题
        if report.unresolved_issues:
            lines.append("【待决议题】")
            for i, issue in enumerate(report.unresolved_issues, 1):
                lines.append(f"  {i}. [{issue.get('agent', '?')}] {issue.get('summary', '')}")
            lines.append("")

        # 可用指令
        lines.append("【您可以执行的指令】")
        for action in report.available_actions:
            lines.append(f"  - {action}")
        lines.append("═" * 65)

        return "\n".join(lines)

    @staticmethod
    def parse_human_command(text: str) -> HumanInstruction:
        """解析人类输入的指令文本"""
        text = text.strip().lower()

        # 尝试匹配已知指令
        command_map = [
            ("continue", HumanCommand.CONTINUE),
            ("approve", HumanCommand.APPROVE),
            ("reject", HumanCommand.REJECT),
            ("revise", HumanCommand.REVISE),
            ("terminate", HumanCommand.TERMINATE),
            ("retry", HumanCommand.RETRY),
            ("skip", HumanCommand.SKIP),
        ]

        for prefix, cmd in command_map:
            if text.startswith(prefix):
                note = text[len(prefix):].strip()
                return HumanInstruction(command=cmd, note=note)

        # goto 指令
        if text.startswith("goto"):
            target = text[len("goto"):].strip()
            return HumanInstruction(
                command=HumanCommand.GOTO,
                target_state=target,
            )

        # detail 指令
        if text.startswith("detail"):
            try:
                n = int(text[len("detail"):].strip())
            except ValueError:
                n = 1
            return HumanInstruction(command=HumanCommand.DETAIL, step_id=n)

        # 无法识别
        return HumanInstruction(command=HumanCommand.CONTINUE, note=f"无法识别指令: {text}")


court_report_generator = CourtReportGenerator()
