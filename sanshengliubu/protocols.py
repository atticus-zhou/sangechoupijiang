"""三省六部 — 消息协议与数据类型

定义了 Agent 之间通信的标准协议和数据结构。
每个消息都有明确的 Speaker(发言者)、MessageType(消息类型)、以及结构化 payload。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


# ============================================================
# 发言者身份
# ============================================================

class Speaker(str, Enum):
    """消息发言者"""
    USER = "user"           # 用户 (皇帝)
    ZHONGSHU = "zhongshu"   # 中书省 — 起草方案
    MENXIA = "menxia"       # 门下省 — 审议方案
    SHANGSHU = "shangshu"   # 尚书省 — 调度执行
    LIBU = "libu"           # 吏部 — 分配子agent
    HUBU = "hubu"           # 户部 — 资源/数据管理
    LIBU_COMM = "libu_comm" # 礼部 — 通信/外交/格式化
    BINGBU = "bingbu"       # 兵部 — 执行/行动
    XINGBU = "xingbu"       # 刑部 — 验证/测试
    GONGBU = "gongbu"       # 工部 — 构建/🖼️图片生成
    SYSTEM = "system"       # 系统消息

    @property
    def display_name(self) -> str:
        names = {
            "user": "用户",
            "zhongshu": "中书省",
            "menxia": "门下省",
            "shangshu": "尚书省",
            "libu": "吏部",
            "hubu": "户部",
            "libu_comm": "礼部",
            "bingbu": "兵部",
            "xingbu": "刑部",
            "gongbu": "工部",
            "system": "系统",
        }
        return names.get(self.value, self.value)

    @property
    def emoji(self) -> str:
        emojis = {
            "user": "👤",
            "zhongshu": "📝",
            "menxia": "⚖️",
            "shangshu": "🏛️",
            "libu": "🎯",
            "hubu": "💰",
            "libu_comm": "📡",
            "bingbu": "⚔️",
            "xingbu": "🔍",
            "gongbu": "🖼️",
            "system": "⚙️",
        }
        return emojis.get(self.value, "💬")

    @property
    def label(self) -> str:
        """带职能标注的显示名"""
        labels = {
            "libu": "🎯 吏部 [分配子Agent]",
            "hubu": "💰 户部 [资源/数据]",
            "libu_comm": "📡 礼部 [通信/外交]",
            "bingbu": "⚔️ 兵部 [执行/行动]",
            "xingbu": "🔍 刑部 [验证/测试]",
            "gongbu": "🖼️ 工部 [构建/图片生成]",
        }
        return labels.get(self.value, self.emoji + " " + self.display_name)


# ============================================================
# 消息类型
# ============================================================

class MessageType(str, Enum):
    """消息类型 — 决定了消息的语义和处理方式"""

    # 奏事 (用户→系统)
    SUBMIT = "submit"           # 用户提交任务

    # 吏部分配
    ALLOCATE = "allocate"       # 吏部 → 系统: 分配子agent
    ALLOCATION_RESULT = "allocation_result"  # 系统 → 吏部: 分配结果

    # 协议消息 (中书↔门下)
    DRAFT_PLAN = "draft_plan"       # 中书省 → 门下省: 方案草案
    REJECT = "reject"                # 门下省 → 中书省: 封驳(驳回)
    APPROVE = "approve"              # 门下省 → 尚书省: 附议(批准)

    # 调度消息 (尚书省↔六部)
    DISPATCH = "dispatch"            # 尚书省 → 六部: 派发任务
    RESULT = "result"                # 六部 → 尚书省: 执行结果
    VERIFY = "verify"                # 尚书省 → 刑部: 验证请求
    VERDICT = "verdict"              # 刑部 → 尚书省: 验证裁决

    # 户部 (资源/数据)
    FETCH_DATA = "fetch_data"       # 尚书省 → 户部: 获取数据
    DATA_READY = "data_ready"       # 户部 → 尚书省: 数据就绪
    TOKEN_REPORT = "token_report"   # 户部 → 尚书省: 预算报告

    # 礼部 (通信/外交)
    FORMAT_OUTPUT = "format_output" # → 礼部: 格式化输出
    OUTPUT_READY = "output_ready"   # 礼部 → : 输出就绪
    EXTERNAL_COM = "external_com"   # → 礼部: 外部通信

    # 工部 (构建/图片生成)
    GENERATE_IMAGE = "generate_image"  # → 工部: 生成图片
    IMAGE_READY = "image_ready"        # 工部 → : 图片就绪
    BUILD = "build"                    # → 工部: 构建/部署

    # 查询消息
    QUERY = "query"             # 请求信息
    RESPONSE = "response"       # 返回信息

    # 系统消息
    SYSTEM = "system"           # 系统通知
    ERROR = "error"             # 错误
    HUMAN = "human"             # 升堂(需要人类介入)
    COMPLETE = "complete"       # 任务完成


# ============================================================
# 核心数据结构
# ============================================================

@dataclass
class CourtMessage:
    """朝堂消息 — Agent 间通信的唯一载体"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    speaker: Speaker = Speaker.SYSTEM
    target: Optional[Speaker] = None  # 显式指定接收者 (优先于路由表)
    msg_type: MessageType = MessageType.SYSTEM
    content: str = ""               # 人类可读的消息正文
    payload: dict = field(default_factory=dict)  # 结构化数据
    reply_to: Optional[str] = None  # 回复的消息 ID
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PlanStep:
    """方案步骤"""
    step_id: int
    assigned_to: str  # "兵部" | "刑部" | "吏部"
    action: str
    detail: str = ""
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"  # pending | in_progress | done | failed


@dataclass
class TaskPlan:
    """中书省起草的方案"""
    task_id: str = ""
    version: int = 1
    title: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    risk_notes: str = ""


@dataclass
class ReviewResult:
    """门下省的审议结果"""
    decision: str = "approve"  # approve | reject
    issues: list[str] = field(default_factory=list)    # 问题列表
    suggestions: list[str] = field(default_factory=list)  # 修改建议


@dataclass
class StepResult:
    """执行步骤的结果"""
    step_id: int = 0
    status: str = "pending"  # done | failed
    summary: str = ""
    detail: dict = field(default_factory=dict)


@dataclass
class CourtEvent:
    """朝堂事件 — 用于生成朝堂报告"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    speaker: Speaker = Speaker.SYSTEM
    action: str = ""
    summary: str = ""
    message_ref: Optional[str] = None


# ============================================================
# 协议辅助函数
# ============================================================

def make_message(
    task_id: str,
    speaker: Speaker,
    msg_type: MessageType,
    content: str,
    payload: dict = None,
    reply_to: str = None,
    target: Speaker = None,
) -> CourtMessage:
    """便捷创建 CourtMessage"""
    return CourtMessage(
        task_id=task_id,
        speaker=speaker,
        target=target,
        msg_type=msg_type,
        content=content,
        payload=payload or {},
        reply_to=reply_to,
    )


def format_agent_message(msg: CourtMessage) -> str:
    """格式化消息为人类可读的聊天文本"""
    speaker_name = msg.speaker.display_name
    emoji = msg.speaker.emoji
    return f"[{emoji} {speaker_name}] {msg.content}"
