"""三省六部系统 — 主入口

组装所有组件, 实现完整的三省六部协作风流。
"""

from __future__ import annotations

import asyncio
import dataclasses
import io
import json
import uuid
import signal
import sys
from datetime import datetime
from typing import Optional

# Windows 控制台 UTF-8 支持
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
except Exception:
    pass

from src.config_manager import config_manager
from src.data.schemas import (
    AgentId,
    SystemState,
    MessageType,
    TaskPlan,
    ReviewResult,
    OrchestratorDecision,
    HumanCommand,
    HumanInstruction,
)
from src.core.state_machine import StateMachine, IllegalTransitionError
from src.core.message_bus import message_bus
from src.core.court_event_log import court_event_log
from src.core.court_report import court_report_generator
from src.core.human_interface import human_interface

from src.agents.zhongshu import ZhongshuAgent
from src.agents.menxia import MenxiaAgent
from src.agents.shangshu import ShangshuAgent
from src.agents.libu import LibuAgent
from src.agents.hubu import HubuAgent
from src.agents.libu_comm import LibuCommAgent
from src.agents.bingbu import BingbuAgent
from src.agents.xingbu import XingbuAgent
from src.agents.gongbu import GongbuAgent


class SanShengLiuBu:
    """三省六部系统主控制器"""

    def __init__(self, office_id: str = ""):
        self.office_id = office_id
        # Agent 实例 — 三省
        self.zhongshu = ZhongshuAgent(office_id=office_id)
        self.menxia = MenxiaAgent(office_id=office_id)
        self.shangshu = ShangshuAgent(office_id=office_id)
        # 六部
        self.libu = LibuAgent(office_id=office_id)             # 吏部 — 记忆与知识
        self.hubu = HubuAgent(office_id=office_id)             # 户部 — 资源与数据
        self.libu_comm = LibuCommAgent(office_id=office_id)    # 礼部 — 通信与接入
        self.bingbu = BingbuAgent(office_id=office_id)         # 兵部 — 执行操作
        self.xingbu = XingbuAgent(office_id=office_id)         # 刑部 — 质量验证
        self.gongbu = GongbuAgent(office_id=office_id)         # 工部 — 建造产出

        # 状态机
        self.state = StateMachine()

        # 注册 agent 到消息总线
        for agent in [self.zhongshu, self.menxia, self.shangshu,
                      self.libu, self.hubu, self.libu_comm,
                      self.bingbu, self.xingbu, self.gongbu]:
            agent.register()

        # 设置吏部存储回调
        message_bus.set_store_callback(self._on_message_store)

        # 设置朝堂报告文档获取器
        court_report_generator.set_doc_fetcher(self.libu.get_task_documents)

        # 当前任务状态
        self.current_task_id: Optional[str] = None
        self.current_plan: Optional[TaskPlan] = None
        self.current_review: Optional[ReviewResult] = None
        self.step_results: dict[int, dict] = {}  # step_id → result
        self.planned_steps_cache: dict[str, TaskPlan] = {}  # task_id → plan
        self.step_retry_counts: dict[int, int] = {}  # step_id → retry count

    async def _on_message_store(self, doc) -> None:
        """消息存储回调 — 写入向量库"""
        pass  # 吏部通过 libu.store_document 处理

    # ============================================================
    # 主流程
    # ============================================================

    async def run(self, user_request: str, task_id: str = None) -> dict:
        """执行完整的三省六部流程"""
        task_id = task_id or str(uuid.uuid4())[:8]
        self.current_task_id = task_id

        print(f"\n{'='*60}")
        print(f"  三省六部系统启动 — 任务: {task_id}")
        print(f"  需求: {user_request[:80]}...")
        print(f"{'='*60}\n")

        try:
            # Phase 1: 方案阶段 (中书省 ⇄ 门下省)
            plan = await self._planning_phase(task_id, user_request)

            # Phase 2: 执行阶段 (尚书省调度 + 兵部/刑部串行)
            result = await self._execution_phase(task_id, plan)

            # Phase 3: 归档
            if result.get("status") != "aborted":
                await self._finalize(task_id, plan, result)
            else:
                self.state.transition(SystemState.TERMINATED, "尚书省终止", AgentId.SHANGSHU)

            return result

        except Exception as e:
            print(f"\n[系统异常] {e}")
            # 避免重复转换: 只有非终止状态才转换
            if not self.state.is_terminal():
                self.state.transition(SystemState.TERMINATED, str(e), AgentId.SHANGSHU)
            return {"status": "error", "error": str(e)}

    # ============================================================
    # Phase 1: 方案阶段
    # ============================================================

    async def _planning_phase(self, task_id: str, user_request: str) -> TaskPlan:
        """中书省起草 + 门下省审议, 最多 5 轮"""
        print("─" * 40)
        print("  Phase 1: 方案阶段 (中书省 ⇄ 门下省)")
        print("─" * 40)

        self.state.transition(SystemState.PLANNING, "开始起草方案", AgentId.ZHONGSHU)
        court_event_log.record(task_id, AgentId.ZHONGSHU, SystemState.RECEIVED,
                               SystemState.PLANNING, "起草", "收到用户需求,中书省开始起草方案")

        # 吏部检索上下文
        context = await self.libu.retrieve_context(user_request)
        context_text = json.dumps(context, ensure_ascii=False, indent=2)

        # 中书省起草初版
        plan = await self.zhongshu.draft_plan(task_id, user_request, context_text)
        print(f"  [中书省] 方案 v{plan.version} 已起草 ({len(plan.steps)} 步骤)")

        # 存储方案
        await self.libu.store_plan(task_id, dataclasses.asdict(plan))

        # 中书-门下循环 (最多5轮)
        round_num = 0
        max_rounds = config_manager.get_system_config().max_zhongshu_menxia_rounds

        while round_num < max_rounds:
            round_num += 1
            self.state.increment_round("zhongshu_menxia")

            # 门下省审议
            self.state.transition(SystemState.REVIEWING, f"第{round_num}轮审议", AgentId.MENXIA)
            court_event_log.record(task_id, AgentId.MENXIA, SystemState.PLANNING,
                                   SystemState.REVIEWING, "审议", f"门下省第{round_num}轮审议方案 v{plan.version}")

            history = await self.libu.query_history(user_request)
            history_text = json.dumps(history, ensure_ascii=False, indent=2)

            review = await self.menxia.review_plan(task_id, plan, history_text)
            self.current_review = review
            await self.libu.store_review(task_id, dataclasses.asdict(review), plan.version)

            print(f"  [门下省] 第{round_num}轮审议: {review.decision} (置信度: {review.confidence})")

            if review.decision == "approve":
                print(f"  [门下省] ✅ 方案批准!")
                self.state.transition(SystemState.APPROVED, "方案批准", AgentId.MENXIA)
                court_event_log.record(task_id, AgentId.MENXIA, SystemState.REVIEWING,
                                       SystemState.APPROVED, "附议", f"门下省第{round_num}轮: 附议批准")
                self.current_plan = plan
                self.planned_steps_cache[task_id] = plan
                return plan

            elif review.decision == "conditional_approve":
                # 部分批准,中书省修订指定的几步
                print(f"  [门下省] ⚠️ 条件批准 — 中书省修订中...")
                self.state.transition(SystemState.REVISING, "条件批准,中书省修订", AgentId.ZHONGSHU)
                plan = await self.zhongshu.revise_plan(task_id, plan, review, context_text)
                await self.libu.store_plan(task_id, dataclasses.asdict(plan))
                # 条件批准后直接认为通过
                self.state.transition(SystemState.APPROVED, "条件批准后方案通过", AgentId.MENXIA)
                self.current_plan = plan
                self.planned_steps_cache[task_id] = plan
                return plan

            else:  # reject
                print(f"  [门下省] ❌ 驳回 — 中书省修订中...")
                if review.issues:
                    for issue in review.issues:
                        print(f"     - {issue.detail}")

                # 检查是否达到上限
                if round_num >= max_rounds:
                    print(f"  ⚠️ 中书-门下已达{max_rounds}轮上限 — 升堂!")
                    # 自动升堂
                    plan = await self._call_human_for_plan(task_id, plan, review, round_num, max_rounds)
                    if plan is None:
                        raise Exception(f"中书-门下{max_rounds}轮无法达成一致,人类终止")
                    # 人类给了新方案或裁决
                    self.state.transition(SystemState.APPROVED, "人类裁决后批准", AgentId.HUMAN)
                    self.current_plan = plan
                    self.planned_steps_cache[task_id] = plan
                    return plan

                # 中书省修订
                self.state.transition(SystemState.REVISING, f"第{round_num}轮驳回,中书省修订", AgentId.ZHONGSHU)
                court_event_log.record(task_id, AgentId.ZHONGSHU, SystemState.REVIEWING,
                                       SystemState.REVISING, "修订", f"中书省根据驳回意见修订方案 (第{round_num}轮)")
                plan = await self.zhongshu.revise_plan(task_id, plan, review, context_text)
                await self.libu.store_plan(task_id, dataclasses.asdict(plan))
                print(f"  [中书省] 方案已修订为 v{plan.version}")

        raise Exception("方案阶段异常退出")

    async def _call_human_for_plan(
        self, task_id: str, plan: TaskPlan, review: ReviewResult,
        round_num: int, max_rounds: int
    ) -> Optional[TaskPlan]:
        """升堂 — 请人类裁决方案分歧"""
        self.state.transition(SystemState.HUMAN_CALLED,
                              f"中书-门下{max_rounds}轮无法达成一致",
                              AgentId.SHANGSHU)

        report = await court_report_generator.generate(task_id, self.state)
        formatted = court_report_generator.format_report(report)
        print(f"\n{formatted}\n")
        print(f"中书-门下已讨论 {round_num} 轮,无法达成一致。")
        print("请裁决: approve (批准当前方案) / reject <意见> (驳回) / revise (直接修改)")

        try:
            cmd_text = await asyncio.to_thread(input, "\n[人类裁决] > ")
        except (EOFError, KeyboardInterrupt):
            return None

        cmd = court_report_generator.parse_human_command(cmd_text)

        if cmd.command == HumanCommand.APPROVE:
            return plan  # 人类强制批准
        elif cmd.command == HumanCommand.REJECT:
            # 人类给意见,中书省修改
            revised = await self.zhongshu.revise_plan(
                task_id, plan,
                ReviewResult(task_id=task_id, plan_version=plan.version,
                             decision="reject", required_changes=[cmd.note]),
                f"人类意见: {cmd.note}"
            )
            return revised
        elif cmd.command == HumanCommand.TERMINATE:
            return None
        else:
            # 默认返回原方案
            return plan

    # ============================================================
    # Phase 2: 执行阶段
    # ============================================================

    async def _execution_phase(self, task_id: str, plan: TaskPlan) -> dict:
        """尚书省 LLM 调度循环 + 兵部/刑部串行"""
        print("\n" + "─" * 40)
        print("  Phase 2: 执行阶段 (尚书省调度)")
        print("─" * 40)

        self.state.transition(SystemState.DISPATCHING, "进入调度阶段", AgentId.SHANGSHU)

        loop_count = 0
        max_loops = config_manager.get_system_config().max_orchestrator_loops
        veto_count = 0
        max_vetos = 3  # VETO 3次后强制终止, 防止死循环
        completed_steps: list[dict] = []
        in_progress_steps: list[dict] = []
        all_results: list[dict] = []
        current_bingbu_output: Optional[dict] = None  # 当前待刑部验证的兵部产出

        while loop_count < max_loops:
            loop_count += 1
            self.state.increment_round("orchestrator")

            # ---- 检查人类打断 ----
            if human_interface.is_interrupted():
                cmd = await human_interface.handle_interrupt(task_id, self.state)
                result = await self._apply_human_command(cmd, task_id, plan)
                if result == "TERMINATE":
                    return {"status": "terminated_by_human"}
                elif result == "CONTINUE":
                    pass
                elif isinstance(result, dict):
                    completed_steps = result.get("completed_steps", completed_steps)
                    in_progress_steps = result.get("in_progress_steps", in_progress_steps)

            # ---- 尚书省决策 ----
            self.state.transition(SystemState.DISPATCHING, f"调度循环{loop_count}", AgentId.SHANGSHU)

            decision = await self.shangshu.decide_next(
                task_id=task_id,
                plan=plan,
                completed_steps=completed_steps,
                in_progress_steps=in_progress_steps,
                last_error="",
                loop_count=loop_count,
            )

            print(f"\n  [尚书省] 循环{loop_count} → {decision.decision}")
            print(f"    推理: {decision.reasoning[:100]}...")

            court_event_log.record(
                task_id, AgentId.SHANGSHU, SystemState.DISPATCHING,
                SystemState.DISPATCHING, "调度决策",
                f"循环{loop_count}: {decision.decision} — {decision.reasoning[:80]}"
            )

            # ---- 执行决策 ----
            match decision.decision:
                case "DISPATCH":
                    await self._handle_dispatch(
                        task_id, plan, decision.targets[0],
                        completed_steps, in_progress_steps, all_results
                    )
                    # 如果派发的是兵部,标记当前待验证的兵部产出
                    if decision.targets[0].department in ("兵部", "bingbu"):
                        target_step = decision.targets[0].step_id
                        current_bingbu_output = self.step_results.get(target_step)

                case "DISPATCH_PARALLEL":
                    # 并行派发 (简化处理: 逐个执行)
                    for target in decision.targets:
                        await self._handle_dispatch(
                            task_id, plan, target,
                            completed_steps, in_progress_steps, all_results
                        )

                case "WAIT":
                    await asyncio.sleep(0.5)

                case "RETRY":
                    target = decision.targets[0] if decision.targets else None
                    if target:
                        step_id = target.step_id
                        self.step_retry_counts[step_id] = self.step_retry_counts.get(step_id, 0) + 1
                        retries = self.step_retry_counts[step_id]
                        if retries > config_manager.get_system_config().max_bingbu_xingbu_retries:
                            # 超过重试上限,升堂
                            print(f"  ⚠️ 步骤{step_id}重试{retries}次,超过上限,升堂!")
                            await self._veto_to_human(task_id, plan, f"步骤{step_id}重试{retries}次失败")
                        else:
                            print(f"  [尚书省] 重试步骤{step_id} (第{retries}次)")
                            await self._handle_dispatch(
                                task_id, plan, target,
                                completed_steps, in_progress_steps, all_results
                            )

                case "REVISE_PLAN":
                    print(f"  [尚书省] 退回中书省修订: {decision.reasoning[:80]}...")
                    self.state.transition(SystemState.PLANNING, decision.reasoning, AgentId.SHANGSHU)
                    plan = await self.zhongshu.revise_plan(
                        task_id, plan,
                        ReviewResult(task_id=task_id, plan_version=plan.version,
                                     decision="reject", required_changes=[decision.reasoning]),
                        ""
                    )
                    self.state.transition(SystemState.APPROVED, "修订方案批准", AgentId.SHANGSHU)
                    # 清空旧步骤状态, 避免新旧方案混杂
                    completed_steps.clear()
                    in_progress_steps.clear()
                    self.step_results.clear()
                    self.step_retry_counts.clear()

                case "VETO":
                    veto_count += 1
                    print(f"  [尚书省] 🛑 否决! ({veto_count}/{max_vetos}) {decision.reasoning[:80]}...")

                    if veto_count >= max_vetos:
                        print(f"  [尚书省] 否决次数达上限({max_vetos}), 强制终止")
                        self.state.transition(SystemState.TERMINATED, f"否决{max_vetos}次达上限", AgentId.SHANGSHU)
                        return {"status": "aborted", "reason": f"否决{max_vetos}次, 任务在当前环境下不可行",
                                "veto_reason": decision.reasoning}

                    self.state.transition(SystemState.SHANGSHU_VETO, decision.reasoning, AgentId.SHANGSHU)

                    if decision.veto_target == "human":
                        if sys.stdin.isatty():
                            await self._veto_to_human(task_id, plan, decision.reasoning)
                        else:
                            print(f"  [尚书省] 非交互环境, 自动终止任务")
                            self.state.transition(SystemState.TERMINATED, decision.reasoning, AgentId.SHANGSHU)
                            return {"status": "aborted", "reason": decision.reasoning,
                                    "note": "需要人类提供数据, 请重新提交并附带数据"}
                    else:  # zhongshu
                        self.state.transition(SystemState.PLANNING, "否决后重新起草", AgentId.SHANGSHU)
                        plan = await self.zhongshu.draft_plan(
                            task_id,
                            f"重新设计方案,原因: {decision.reasoning}\n原方案: {dataclasses.asdict(plan)}",
                            ""
                        )
                        self.state.transition(SystemState.APPROVED, "否决后新方案直接批准", AgentId.SHANGSHU)
                        completed_steps.clear()
                        in_progress_steps.clear()
                        self.step_results.clear()
                        self.step_retry_counts.clear()

                case "ESCALATE_REVIEW":
                    print(f"  [尚书省] ⚖️ 升级审议...")
                    history = await self.libu.query_history(decision.reasoning)
                    review = await self.menxia.review_plan(task_id, plan, json.dumps(history, ensure_ascii=False))
                    if review.decision != "approve":
                        self.state.transition(SystemState.PLANNING, "升级审议驳回,修订方案", AgentId.MENXIA)
                        plan = await self.zhongshu.revise_plan(task_id, plan, review, "")
                        self.state.transition(SystemState.APPROVED, "修订后批准", AgentId.SHANGSHU)

                case "FINALIZE":
                    print(f"  [尚书省] 📊 收尾汇总...")
                    self.state.transition(SystemState.FINALIZING, "所有步骤完成,汇总", AgentId.SHANGSHU)
                    break

                case "ABORT":
                    print(f"  [尚书省] ⛔ 终止: {decision.reasoning}")
                    self.state.transition(SystemState.TERMINATED, decision.reasoning, AgentId.SHANGSHU)
                    return {"status": "aborted", "reason": decision.reasoning}

                case _:
                    print(f"  [尚书省] 未知决策: {decision.decision}")

        # ---- 汇总 ----
        if loop_count >= max_loops:
            print(f"  ⚠️ 调度循环达上限({max_loops}), 强制收尾")
            self.state.transition(SystemState.FINALIZING, f"循环耗尽({max_loops}轮),强制收尾", AgentId.SHANGSHU)
        shangshu_summary = await self.shangshu.finalize(task_id, plan, all_results)
        final_report = self._select_primary_deliverable(all_results) or shangshu_summary
        self.state.transition(SystemState.DELIVERING, "交付用户", AgentId.SHANGSHU)
        return {
            "status": "completed",
            "task_id": task_id,
            "plan": dataclasses.asdict(plan),
            "results": all_results,
            "final_report": final_report,
            "orchestrator_summary": shangshu_summary,
        }

    @staticmethod
    def _select_primary_deliverable(all_results: list[dict]) -> str:
        """Prefer the actual builder/executor deliverable over orchestration summaries."""
        for result in reversed(all_results):
            if result.get("department") in ("工部", "gongbu") and result.get("content"):
                return result["content"]
        for result in reversed(all_results):
            if result.get("output"):
                return result["output"]
        return ""

    async def _handle_dispatch(
        self, task_id: str, plan: TaskPlan, target,
        completed_steps: list, in_progress_steps: list, all_results: list
    ):
        """处理单次派发: 兵部执行 → 刑部验证 或直接执行"""
        step_id = target.step_id
        department = target.department

        # 更新步骤状态
        for step in plan.steps:
            if step.step_id == step_id:
                step.status = "in_progress"
                break

        in_progress_steps.append({
            "step_id": step_id, "department": department,
            "action": target.instruction, "status": "in_progress",
        })

        if department in ("兵部", "bingbu"):
            # 兵部执行
            print(f"  [兵部] 执行步骤{step_id}: {target.instruction[:60]}...")
            self.state.transition(SystemState.EXECUTING, f"兵部执行步骤{step_id}", AgentId.BINGBU)

            bingbu_result = await self.bingbu.execute_step(
                task_id=task_id, step_id=step_id, instruction=target.instruction
            )
            self.step_results[step_id] = bingbu_result
            await self.libu.store_agent_output(task_id, step_id, bingbu_result, AgentId.BINGBU)

            # 更新步骤状态
            for step in plan.steps:
                if step.step_id == step_id:
                    step.status = "executed"
                    break

            # 兵部执行完 → 立即刑部验证 (串行规则)
            print(f"  [刑部] 验证步骤{step_id}...")
            self.state.transition(SystemState.TESTING, f"刑部验证步骤{step_id}", AgentId.XINGBU)

            verify_result = await self.xingbu.verify_step(
                task_id=task_id, step_id=step_id, bingbu_output=bingbu_result
            )
            await self.libu.store_agent_output(task_id, step_id, verify_result, AgentId.XINGBU)

            verdict = verify_result.get("verdict", "fail")
            print(f"  [刑部] 步骤{step_id}验证: {verdict}")

            if verdict == "pass":
                for step in plan.steps:
                    if step.step_id == step_id:
                        step.status = "verified"
                        break
                completed_steps.append({
                    "step_id": step_id, "assigned_to": "兵部",
                    "action": target.instruction,
                    "status": "verified",
                    "result_summary": bingbu_result.get("summary", ""),
                })
                all_results.append({
                    "step_id": step_id, "status": "verified",
                    "summary": bingbu_result.get("summary", ""),
                    "department": "兵部",
                    "output": bingbu_result.get("output", ""),
                    "context_refs": bingbu_result.get("context_refs", []),
                    "sources": bingbu_result.get("sources", []),
                    "data_points": bingbu_result.get("data_points", []),
                    "chart_suggestions": bingbu_result.get("chart_suggestions", []),
                    "competitors": bingbu_result.get("competitors", []),
                    "notes": bingbu_result.get("notes", ""),
                    "verification": verify_result,
                })
                self.step_retry_counts[step_id] = 0  # 重置重试计数
            else:
                # 验证失败 — 尚书省下次循环会决定 RETRY 还是其他
                for step in plan.steps:
                    if step.step_id == step_id:
                        step.status = "failed"
                        break
                all_results.append({
                    "step_id": step_id, "status": "failed",
                    "summary": f"验证失败: {verify_result.get('test_summary', '')}",
                })

        elif department in ("刑部", "xingbu"):
            # 查找此步骤依赖的前序兵部步骤的产出
            dep_output = {}
            for s in plan.steps:
                if s.step_id == step_id and s.depends_on:
                    for dep_id in s.depends_on:
                        if dep_id in self.step_results:
                            dep_output = self.step_results[dep_id]
                            break
            # 没找到依赖 → 尝试所有已完成步骤的产出
            if not dep_output:
                for r in all_results:
                    sid = r.get("step_id")
                    if sid and sid in self.step_results:
                        dep_output = self.step_results[sid]
                        break

            self.state.transition(SystemState.TESTING, f"刑部执行步骤{step_id}", AgentId.XINGBU)
            verify_result = await self.xingbu.verify_step(
                task_id=task_id, step_id=step_id,
                bingbu_output=dep_output or {},
                context=target.instruction,
            )
            completed_steps.append({
                "step_id": step_id, "assigned_to": "刑部",
                "action": target.instruction,
                "status": verify_result.get("verdict", "completed"),
            })
            all_results.append({
                "step_id": step_id, "status": verify_result.get("verdict", "completed"),
                "summary": verify_result.get("test_summary", ""),
            })

        elif department in ("吏部", "libu"):
            print(f"  [吏部] 查询步骤{step_id}: {target.instruction[:60]}...")
            results = await self.libu.retrieve_context(target.instruction, task_id)
            for step in plan.steps:
                if step.step_id == step_id:
                    step.status = "verified"
                    break
            completed_steps.append({
                "step_id": step_id, "assigned_to": "吏部",
                "action": target.instruction,
                "status": "verified",
                "result_summary": f"检索到 {len(results)} 条相关上下文",
            })
            all_results.append({
                "step_id": step_id, "status": "completed",
                "summary": f"吏部查询完成: {len(results)} 条结果",
            })

        elif department in ("户部", "hubu"):
            print(f"  [户部] 资源操作步骤{step_id}: {target.instruction[:60]}...")
            result = await self.hubu.read_file(target.instruction, task_id)
            for step in plan.steps:
                if step.step_id == step_id:
                    step.status = "verified"
                    break
            completed_steps.append({
                "step_id": step_id, "assigned_to": "户部",
                "action": target.instruction,
                "status": "verified",
                "result_summary": result.get("result", "")[:100],
            })
            all_results.append({
                "step_id": step_id, "status": "completed",
                "summary": "户部资源操作完成",
            })

        elif department in ("工部", "gongbu"):
            print(f"  [工部] 产出步骤{step_id}: {target.instruction[:60]}...")
            # 收集前面步骤的真实产出数据，传给工部作为素材
            collected_data_parts = []
            for r in all_results:
                sid = r.get("step_id")
                if sid and sid in self.step_results:
                    step_data = self.step_results[sid]
                    collected_data_parts.append(
                        f"## 步骤{sid}产出\n{step_data.get('output', step_data.get('summary', ''))}"
                    )
            real_data = "\n\n".join(collected_data_parts) if collected_data_parts else target.instruction

            result = await self.gongbu.generate_report(
                title=plan.title,
                data=real_data,
                task_id=task_id,
            )
            self.step_results[step_id] = result
            for step in plan.steps:
                if step.step_id == step_id:
                    step.status = "verified"
                    break
            completed_steps.append({
                "step_id": step_id, "assigned_to": "工部",
                "action": target.instruction,
                "status": "verified",
                "result_summary": result.get("summary", ""),
            })
            all_results.append({
                "step_id": step_id, "status": "completed",
                "summary": f"工部产出完成: {result.get('summary', '')}",
                "department": "工部",
                "content": result.get("content", ""),
                "files_created": result.get("files_created", []),
                "task_type": result.get("task_type", "report"),
            })

        elif department in ("礼部", "礼部"):
            print(f"  [礼部] 通信步骤{step_id}: {target.instruction[:60]}...")
            result = await self.libu_comm.format_response("web", target.instruction, task_id)
            for step in plan.steps:
                if step.step_id == step_id:
                    step.status = "verified"
                    break
            completed_steps.append({
                "step_id": step_id, "assigned_to": "礼部",
                "action": target.instruction,
                "status": "verified",
                "result_summary": "消息格式化完成",
            })
            all_results.append({
                "step_id": step_id, "status": "completed",
                "summary": "礼部通信处理完成",
            })

        # 清理 in_progress
        in_progress_steps[:] = [s for s in in_progress_steps if s["step_id"] != step_id]

    async def _veto_to_human(self, task_id: str, plan: TaskPlan, reason: str):
        """尚书省否决 → 升堂"""
        if not sys.stdin.isatty():
            print(f"  [升堂] 非交互环境, 自动终止: {reason[:80]}")
            self.state.transition(SystemState.TERMINATED, f"非交互环境自动终止: {reason}", AgentId.SHANGSHU)
            raise Exception(f"升堂请求在非交互环境: {reason}")
        self.state.transition(SystemState.HUMAN_CALLED, reason, AgentId.SHANGSHU)
        cmd = await human_interface.present_and_wait(task_id, self.state)
        await self._apply_human_command(cmd, task_id, plan)

    async def _apply_human_command(self, cmd: HumanInstruction, task_id: str, plan: TaskPlan) -> str | dict:
        """应用人类指令"""
        match cmd.command:
            case HumanCommand.CONTINUE:
                return "CONTINUE"
            case HumanCommand.TERMINATE:
                self.state.transition(SystemState.TERMINATED, "人类终止", AgentId.HUMAN)
                return "TERMINATE"
            case HumanCommand.RETRY:
                return "RETRY"
            case HumanCommand.SKIP:
                return "SKIP"
            case HumanCommand.GOTO:
                try:
                    target = SystemState(cmd.target_state)
                    self.state.force_transition(target, f"人类跳转到 {target.value}")
                    return "CONTINUE"
                except ValueError:
                    return "CONTINUE"
            case _:
                return "CONTINUE"

    # ============================================================
    # Phase 3: 收尾
    # ============================================================

    async def _finalize(self, task_id: str, plan: TaskPlan, result: dict):
        """归档并输出最终报告 — 优先使用工部/兵部产出的实际内容"""
        print("\n" + "=" * 60)
        print("  最终报告")
        print("=" * 60)

        # 从步骤结果中提取工部或兵部的实际产出作为报告内容
        all_results = result.get("results", [])
        actual_content = ""
        # 优先用工部产出
        for r in all_results:
            sid = r.get("step_id")
            if sid and sid in self.step_results:
                step_data = self.step_results[sid]
                # 工部或兵部产出的实际内容
                if step_data.get("content") or step_data.get("output"):
                    actual_content = step_data.get("content") or step_data.get("output", "")
                    break
        # 兜底用尚书省总结
        final_report = actual_content or result.get("final_report", "")

        if final_report:
            print(final_report[:2000])
            if len(final_report) > 2000:
                print(f"\n  ... (共 {len(final_report)} 字, 完整内容见文件)")
            # 写入磁盘
            try:
                from pathlib import Path
                import re
                out_dir = Path("output") / task_id
                out_dir.mkdir(parents=True, exist_ok=True)
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', plan.title or "report")[:40]
                report_path = out_dir / f"{safe_title}.md"
                # 把尚书省总结附在后面作为执行摘要
                full_text = final_report
                if actual_content and result.get("final_report"):
                    full_text = final_report  # 已是实际内容
                report_path.write_text(full_text, encoding="utf-8")
                print(f"\n  [工部] 报告已保存: {report_path}")
            except Exception as e:
                print(f"\n  [工部] 报告保存失败: {e}")
        else:
            print(f"\n  任务: {task_id}")
            print(f"  方案: {plan.title}")
            print(f"  状态: {result.get('status', 'unknown')}")
            print(f"  步骤: {len(result.get('results', []))} 步")

        # 吏部归档
        archive_msg = await self.libu.archive_task(task_id)
        print(f"\n  [吏部] {archive_msg}")

        self.state.transition(SystemState.COMPLETED, "任务完成", AgentId.SHANGSHU)
        print(f"\n  系统状态: {self.state.summary()}")
        print("=" * 60)


# ============================================================
# 交互式入口
# ============================================================

async def interactive_mode():
    """交互模式 — 支持人类随时打断"""
    system = SanShengLiuBu()

    # 注册信号处理 (Ctrl+C 打断)
    def signal_handler(sig, frame):
        print("\n\n[打断] 正在生成朝堂报告...")
        human_interface.request_interrupt()

    signal.signal(signal.SIGINT, signal_handler)

    print("╔══════════════════════════════════════════════════════╗")
    print("║        🏛️  三省六部 · 多 Agent 协作系统              ║")
    print("║                                                      ║")
    print("║  中书省(起草) → 门下省(审议) → 尚书省(调度)          ║")
    print("║  六部: 吏部(记忆) 户部(资源) 礼部(通信)              ║")
    print("║        兵部(执行) 刑部(测试) 工部(构建)              ║")
    print("║                                                      ║")
    print("║  输入 /help 查看指令  |  Ctrl+C 打断并查看朝堂报告    ║")
    print("╚══════════════════════════════════════════════════════╝")

    while True:
        try:
            user_input = await asyncio.to_thread(input, "\n[奏事] > ")
        except (EOFError, KeyboardInterrupt):
            print("\n退朝。")
            break

        if not user_input.strip():
            continue

        if user_input.startswith("/"):
            await handle_slash_command(user_input, system)
        else:
            result = await system.run(user_input)
            if result.get("final_report"):
                print(f"\n[最终报告]\n{result['final_report']}")


async def handle_slash_command(cmd: str, system: SanShengLiuBu):
    """处理斜杠指令"""
    cmd = cmd.lower().strip()

    if cmd == "/help":
        print("""
可用指令:
  /help       — 显示此帮助
  /status     — 查看当前任务状态 (朝堂报告)
  /continue   — 继续当前流程
  /terminate  — 终止当前任务
  /detail <n> — 查看最近第 n 步详情
  /quit       — 退出系统

直接输入需求即可启动三省六部流程。
Ctrl+C 可在任意时刻打断并查看朝堂报告。""")

    elif cmd == "/status":
        if system.current_task_id and not system.state.is_terminal():
            report = await court_report_generator.generate(
                system.current_task_id, system.state
            )
            print(court_report_generator.format_report(report))
        else:
            print("当前无进行中的任务。")

    elif cmd == "/continue":
        human_interface.clear_interrupt()

    elif cmd == "/terminate":
        if system.current_task_id:
            system.state.transition(SystemState.TERMINATED, "人类指令终止", AgentId.HUMAN)
        print("任务已终止。")

    elif cmd.startswith("/detail"):
        n = 1
        try:
            n = int(cmd.split()[1])
        except (IndexError, ValueError):
            pass
        if system.current_task_id:
            events = court_event_log.get_recent(system.current_task_id, n)
            for e in events:
                print(f"  [{e.timestamp}] {e.agent.value}: {e.summary}")
                if e.detail:
                    print(f"    详情: {json.dumps(e.detail, ensure_ascii=False, indent=4)}")

    elif cmd == "/quit":
        print("退朝。")
        sys.exit(0)

    else:
        print(f"未知指令: {cmd}，输入 /help 查看可用指令。")


# ============================================================
# 非交互式入口
# ============================================================

async def run_once(user_request: str) -> dict:
    """非交互式执行单次任务"""
    system = SanShengLiuBu()
    return await system.run(user_request)


def main():
    """入口"""
    if len(sys.argv) > 1:
        # 命令行模式: python -m src.main "修复订单超时"
        request = " ".join(sys.argv[1:])
        result = asyncio.run(run_once(request))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 交互模式
        try:
            asyncio.run(interactive_mode())
        except KeyboardInterrupt:
            print("\n退朝。")


if __name__ == "__main__":
    main()
