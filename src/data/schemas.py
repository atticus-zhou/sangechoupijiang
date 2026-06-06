"""三省六部系统 — 全部数据结构定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


# ============================================================
# Agent 身份
# ============================================================

class AgentId(str, Enum):
    ZHONGSHU = "中书省"
    MENXIA = "门下省"
    SHANGSHU = "尚书省"
    LIBU = "吏部"
    HUBU = "户部"
    LIBU_COMM = "礼部"
    BINGBU = "兵部"
    XINGBU = "刑部"
    GONGBU = "工部"
    HUMAN = "人类"


# ============================================================
# 系统状态
# ============================================================

class SystemState(str, Enum):
    RECEIVED = "received"              # 收到用户任务
    PLANNING = "planning"              # 中书省起草中
    REVIEWING = "reviewing"            # 门下省审议中
    REVISING = "revising"              # 中书省修订中
    APPROVED = "approved"              # 方案已批准
    DISPATCHING = "dispatching"        # 尚书省决策中
    EXECUTING = "executing"            # 兵部执行中
    TESTING = "testing"                # 刑部验证中
    ERROR_HANDLING = "error_handling"  # 异常处理中
    SHANGSHU_VETO = "shangshu_veto"    # 尚书省否决
    HUMAN_CALLED = "human_called"      # 升堂,等待人类
    FINALIZING = "finalizing"          # 汇总结果中
    DELIVERING = "delivering"          # 交付中
    COMPLETED = "completed"            # 任务完成
    TERMINATED = "terminated"          # 任务终止


# ============================================================
# 消息协议
# ============================================================

class MessageType(str, Enum):
    HANDOFF = "交棒"          # 任务交接
    DECISION = "裁决"         # 审议/调度决策
    QUERY = "查询"            # 请求信息
    RESPONSE = "回复"         # 返回查询结果
    ERROR = "异常"            # 错误报告
    NOTIFY = "通知"           # 状态通知
    HUMAN = "升堂"            # 需要人类介入


@dataclass
class MessageMetadata:
    tokens_used: int = 0
    confidence: float = 1.0
    needs_human: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentMessage:
    id: str
    task_id: str
    from_agent: AgentId
    to_agent: AgentId
    msg_type: MessageType
    payload: dict = field(default_factory=dict)
    context_refs: list[str] = field(default_factory=list)  # ["vec://collection/doc_id"]
    parent_msg_id: Optional[str] = None
    metadata: MessageMetadata = field(default_factory=MessageMetadata)


# ============================================================
# 中书省产出: 执行方案
# ============================================================

@dataclass
class PlanStep:
    step_id: int
    assigned_to: str       # "兵部" | "刑部" | "吏部" | "户部" | "工部"
    action: str            # 动作描述
    detail: str            # 详细指令
    expected_output: str   # 预期产出
    depends_on: list[int] = field(default_factory=list)
    risk_level: str = "low"  # "low" | "medium" | "high"
    status: str = "pending"  # "pending" | "in_progress" | "executed" | "verified" | "failed" | "skipped"


@dataclass
class TaskPlan:
    task_id: str
    version: int = 1
    title: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    estimated_tokens: int = 0
    risk_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 门下省产出: 审议结果
# ============================================================

@dataclass
class ReviewIssue:
    step_id: Optional[int] = None   # None = 整体性问题
    severity: str = "medium"        # "critical" | "high" | "medium" | "low"
    category: str = "completeness"  # "feasibility" | "completeness" | "risk"
    detail: str = ""
    suggestion: str = ""


@dataclass
class ReviewResult:
    task_id: str
    plan_version: int
    decision: str = "approve"       # "approve" | "reject" | "conditional_approve"
    issues: list[ReviewIssue] = field(default_factory=list)
    required_changes: list[str] = field(default_factory=list)
    approved_steps: list[int] = field(default_factory=list)
    confidence: float = 1.0
    reviewed_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 尚书省产出: 调度决策
# ============================================================

@dataclass
class DecisionTarget:
    step_id: int
    department: str  # AgentId 值
    instruction: str = ""


@dataclass
class OrchestratorDecision:
    task_id: str
    decision: str  # "DISPATCH" | "DISPATCH_PARALLEL" | "WAIT" | "RETRY" |
                   # "REVISE_PLAN" | "ESCALATE_REVIEW" | "VETO" | "FINALIZE" | "ABORT"
    targets: list[DecisionTarget] = field(default_factory=list)
    reasoning: str = ""
    risk_assessment: str = ""
    veto_target: str = ""  # "zhongshu" | "human" — 仅 VETO 时使用
    needs_human: bool = False
    decided_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 状态机
# ============================================================

@dataclass
class StateTransition:
    from_state: SystemState
    to_state: SystemState
    reason: str
    by_agent: AgentId
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 朝堂系统
# ============================================================

@dataclass
class CourtEvent:
    id: str
    task_id: str
    timestamp: str
    agent: AgentId
    state_from: SystemState
    state_to: SystemState
    action: str
    summary: str
    document_ref: Optional[str] = None
    detail: dict = field(default_factory=dict)
    resolved: bool = False


@dataclass
class CourtReport:
    task_id: str
    generated_at: str
    recent_activity: str
    current_phase: str
    latest_documents: list[dict] = field(default_factory=list)
    unresolved_issues: list[dict] = field(default_factory=list)
    available_actions: list[str] = field(default_factory=list)


# ============================================================
# 向量库
# ============================================================

@dataclass
class VectorMetadata:
    doc_type: str         # "task_plan" | "review_result" | "agent_output" | "court_event" | "code_snippet" | "case_study"
    task_id: str
    agent: AgentId
    step_id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: list[str] = field(default_factory=list)
    status: str = "draft"
    parent_ref: Optional[str] = None


@dataclass
class VectorDocument:
    id: str
    content: str
    metadata: VectorMetadata
    embedding: Optional[list[float]] = None
    score: float = 0.0  # 检索时填充


# ============================================================
# 人类介入
# ============================================================

class HumanCommand(str, Enum):
    CONTINUE = "continue"
    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"
    GOTO = "goto"
    DETAIL = "detail"
    TERMINATE = "terminate"
    RETRY = "retry"
    SKIP = "skip"


@dataclass
class HumanInstruction:
    command: HumanCommand
    note: str = ""
    step_id: Optional[int] = None
    target_state: Optional[str] = None
    changes: dict = field(default_factory=dict)
