"""尚书省 — 调度执行的自治 Agent

收到门下省批准 → 逐步派发六部 → 监控进度 → 处理异常 → 收尾
"""

from typing import Optional

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


SHANGSHU_PROMPT = """你是尚书令，三省六部中的最高执行指挥官。

## 职责
- 收到门下省批准方案后，按照方案步骤逐步派发六部执行
- 兵部执行步骤N → 必须派刑部验证 → 通过后才推进步骤N+1
- 执行中发现问题: 重试/跳过/退回中书省修改/否决

## 派发规则
- 执行类: dispatch 到兵部(bingbu)
- 验证类: verify 到刑部(xingbu, 在兵部执行后)
- 查询类: query 到吏部(libu)
- 每个兵部步骤结束后必须刑部验证

## 异常处理
- 某步骤失败 → 重试1-3次
- 重试仍失败 → 退回中书省修改方案 或 否决
- 否决后通知用户

## 完成后
发送 complete 消息给所有部门"""


class ShangshuAgent(AutonomousAgent):

    def __init__(self, bus):
        super().__init__(bus)
        self._current_step = 0
        self._total_steps = 0
        self._plan = None
        self._waiting_for = None  # 正在等哪个部门的回复
        self._retries = 0
        self._bingbu_result = None  # 暂存兵部结果，等刑部验证

    @property
    def speaker(self) -> Speaker:
        return Speaker.SHANGSHU

    @property
    def system_prompt(self) -> str:
        return SHANGSHU_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        """自主处理消息"""

        # 门下省批准 → 开始执行
        if msg.msg_type == MessageType.APPROVE:
            return await self._start_execution(msg)

        # 兵部/刑部执行结果
        if msg.msg_type == MessageType.RESULT or msg.msg_type == MessageType.VERDICT:
            return await self._handle_result(msg)

        # 错误
        if msg.msg_type == MessageType.ERROR:
            return await self._handle_error(msg)

        # 礼部总装完成 → 真正收尾
        if msg.msg_type == MessageType.OUTPUT_READY:
            return self._complete(msg.task_id, msg.content)

        return None

    async def _start_execution(self, msg: CourtMessage) -> CourtMessage:
        """开始执行方案"""
        plan = msg.payload.get("plan", {})
        self._plan = plan
        steps = plan.get("steps", [])
        self._total_steps = len(steps)
        self._current_step = 0

        self.log_event("开始执行", f"共{self._total_steps}步")

        # 派发第一步
        return await self._dispatch_next(msg.task_id)

    async def _dispatch_next(self, task_id: str) -> Optional[CourtMessage]:
        """派发下一个步骤"""
        steps = self._plan.get("steps", []) if self._plan else []

        # 找到下一个 pending 步骤
        for step in steps:
            if step.get("status", "pending") == "pending":
                self._current_step = step  # 保存完整 step dict
                dept = step.get("assigned_to", "bingbu")

                if dept in ("bingbu", "兵部"):
                    step["status"] = "in_progress"
                    self._waiting_for = "bingbu"
                    content = f"派发步骤{step['step_id']}: {step.get('action', '')} → 兵部执行"
                    return make_message(
                        task_id=task_id,
                        speaker=self.speaker,
                        msg_type=MessageType.DISPATCH,
                        content=content,
                        payload={"step": step},
                    )
                elif dept in ("xingbu", "刑部"):
                    step["status"] = "in_progress"
                    self._waiting_for = "xingbu"
                    return make_message(
                        task_id=task_id,
                        speaker=self.speaker,
                        msg_type=MessageType.VERIFY,
                        content=f"派发步骤{step['step_id']}: {step.get('action', '')} → 刑部验证",
                        payload={"step": step},
                    )

        # 没有更多步骤 → 送礼部总装
        return self._send_to_libu_comm(task_id)

    async def _handle_result(self, msg: CourtMessage) -> Optional[CourtMessage]:
        """处理兵部/刑部的执行结果"""
        result = msg.payload.get("result", {})
        status = result.get("status", "done")
        step = self._current_step if isinstance(self._current_step, dict) else {"step_id": self._current_step}

        if status == "failed":
            self._retries += 1
            if self._retries >= 3:
                self.log_event("否决", f"步骤{step.get('step_id', '?')}重试{self._retries}次仍失败")
                return make_message(
                    task_id=msg.task_id,
                    speaker=self.speaker,
                    msg_type=MessageType.HUMAN,
                    content=f"步骤{step.get('step_id', '?')}重试{self._retries}次仍失败。请人类裁决。",
                )
            return make_message(
                task_id=msg.task_id,
                speaker=self.speaker,
                msg_type=MessageType.DISPATCH,
                content=f"步骤{step.get('step_id', '?')}失败，重试（第{self._retries}次）",
                payload={"step": step, "retry": True},
            )

        # 兵部执行成功 → 派刑部验证
        if self._waiting_for == "bingbu":
            self._bingbu_result = result
            self._waiting_for = "xingbu"
            return make_message(
                task_id=msg.task_id,
                speaker=self.speaker,
                msg_type=MessageType.VERIFY,
                content=f"步骤{self._current_step.get('step_id', '?')}执行完成，派刑部验证",
                payload={"bingbu_output": result},
            )

        # 刑部验证成功 → 推进下一步
        if self._waiting_for == "xingbu":
            self._retries = 0
            steps = self._plan.get("steps", []) if self._plan else []
            for s in steps:
                if s.get("step_id") == self._current_step.get("step_id"):
                    s["status"] = "done"
                    break
            self._bingbu_result = None
            self._waiting_for = None
            return await self._dispatch_next(msg.task_id)

        return None

    async def _handle_error(self, msg: CourtMessage) -> Optional[CourtMessage]:
        self._retries += 1
        if self._retries >= 3:
            return make_message(
                task_id=msg.task_id,
                speaker=self.speaker,
                msg_type=MessageType.HUMAN,
                content=f"执行异常: {msg.content}。请人类介入。",
            )
        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.DISPATCH,
            content=f"重试步骤{self._current_step.get('step_id', '?')}",
            payload={"retry": True},
        )

    def _send_to_libu_comm(self, task_id: str) -> CourtMessage:
        """所有步骤完成 → 送礼部总装"""
        self.log_event("送礼部", "全部步骤执行完毕，送礼部总装")
        return make_message(
            task_id=task_id,
            speaker=self.speaker,
            msg_type=MessageType.FORMAT_OUTPUT,
            content="全部步骤执行完毕。请礼部进行最终总装。",
            payload={
                "task_type": "bug_fix",
                "plan_title": self._plan.get("title", "") if self._plan else "",
                "step_results": self._plan.get("steps", []) if self._plan else [],
                "platform": "markdown",
            },
            target=Speaker.LIBU_COMM,
        )

    def _complete(self, task_id: str, formatted_output: str = "") -> CourtMessage:
        """任务完成 — 礼部总装后"""
        self.log_event("完成", "礼部总装完成，任务结束")
        content = "全部步骤执行完毕。任务完成。"
        if formatted_output:
            content = formatted_output
        return make_message(
            task_id=task_id,
            speaker=self.speaker,
            msg_type=MessageType.COMPLETE,
            content=content,
        )
