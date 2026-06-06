"""吏部 — 🎯 分配子Agent

吏部是三省六部中第一个响应任务的部门。
收到用户奏事后，分析任务需求，决定需要调动哪些部门参与。

职能:
- 分析任务类型，确定需要哪些子 Agent
- 维护 Agent 能力画像 (每个 Agent 擅长什么)
- 动态分配和调度 Agent 资源
- 管理向量库上下文检索
"""

from typing import Optional
from ..llm.providers import LLMMessage

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


LIBU_PROMPT = """你是吏部尚书，三省六部中的人事主管。你的职责是分析任务需求，决定调动哪些部门。

## 你的核心职责: 分配子Agent
收到用户奏事后，你要判断这个任务需要哪些部门参与:

- 兵部(bingbu): 需要写代码、执行命令、操作文件 → 调用
- 刑部(xingbu): 需要测试、审查、安全检查 → 调用
- 户部(hubu): 需要获取外部数据、管理资源 → 调用
- 礼部(libu_comm): 需要格式化输出、外部通信 → 调用
- 工部(gongbu): 需要构建部署、生成图片/图表 → 调用

## 分配原则
- 根据任务性质判断需要哪些部门
- 不需要的部门不调用，节省资源
- 简单任务可能只需要兵部+刑部
- 复杂任务可能需要全部六部

## 输出格式
{
    "task_type": "bug_fix | feature | review | deploy | image_gen | ...",
    "required_agents": ["bingbu", "xingbu", ...],
    "reason": "为什么需要这些部门"
}"""


class LibuAgent(AutonomousAgent):

    def __init__(self, bus):
        super().__init__(bus)
        # Agent 能力画像
        self.agent_capabilities = {
            "bingbu": ["写代码", "执行命令", "搜索代码", "文件操作"],
            "xingbu": ["测试", "代码审查", "安全检查", "合规验证"],
            "hubu": ["获取数据", "API调用", "数据库查询", "Token管理"],
            "libu_comm": ["格式化输出", "PR生成", "外部通知", "多平台适配"],
            "gongbu": ["构建部署", "图片生成", "数据图表", "宣传图", "流程图", "架构图"],
        }

    @property
    def speaker(self) -> Speaker:
        return Speaker.LIBU

    @property
    def system_prompt(self) -> str:
        return LIBU_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        """收到奏事 → 分析并分配子Agent"""

        if msg.msg_type == MessageType.SUBMIT:
            return await self._allocate_agents(msg)

        if msg.msg_type == MessageType.QUERY:
            return await self._query_context(msg)

        return None

    async def _allocate_agents(self, msg: CourtMessage) -> CourtMessage:
        """分析任务，决定需要哪些部门"""
        user_request = msg.content

        # 关键词匹配分配逻辑
        required = set()

        # 默认都需要的基础部门
        required.add("bingbu")  # 执行部门

        # 按任务类型匹配
        request_lower = user_request.lower()

        if any(kw in request_lower for kw in ["测试", "test", "验证", "检查", "审查"]):
            required.add("xingbu")

        if any(kw in request_lower for kw in ["数据", "data", "api", "查询", "数据库"]):
            required.add("hubu")

        if any(kw in request_lower for kw in ["汇报", "报告", "pr", "发布", "通知", "文档"]):
            required.add("libu_comm")

        if any(kw in request_lower for kw in ["图片", "图表", "架构图", "宣传", "image", "chart", "部署", "构建", "build"]):
            required.add("gongbu")

        # 代码类任务默认需要刑部验证
        if any(kw in request_lower for kw in ["修复", "fix", "bug", "代码", "code", "开发", "feature", "功能"]):
            required.add("xingbu")

        # LLM 辅助决策 (如果有)
        if self._llm:
            try:
                prompt = f"""用户需求: {user_request}

可用部门及其能力:
{self.agent_capabilities}

请判断需要哪些部门参与。输出 JSON。"""
                result = await self._llm.chat([
                    LLMMessage(role='system', content=self.system_prompt),
                    LLMMessage(role='user', content=prompt),
                ])
                # TBD: 解析 LLM 结果
            except Exception:
                pass

        required_list = sorted(required)
        self.log_event("分配", f"任务需要: {required_list}")

        dept_desc = {
            "bingbu": "⚔️ 兵部[执行]", "xingbu": "🔍 刑部[验证]",
            "hubu": "💰 户部[资源]", "libu_comm": "📡 礼部[通信]",
            "gongbu": "🖼️ 工部[图片/构建]",
        }

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.ALLOCATION_RESULT,
            content=f"🎯 吏部已分析任务，调动以下部门:\n" +
                    "\n".join(f"  • {dept_desc.get(d, d)}" for d in required_list) +
                    f"\n\n共 {len(required_list)} 个部门待命。转中书省起草方案。",
            payload={
                "original_request": user_request,
                "required_agents": required_list,
                "task_type": self._classify_task(user_request),
            },
            reply_to=msg.id,
        )

    async def _query_context(self, msg: CourtMessage) -> CourtMessage:
        """检索向量库上下文"""
        query = msg.payload.get("query", msg.content)
        self.log_event("检索", f"查询: {query[:50]}...")
        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.RESPONSE,
            content=f"📚 上下文检索完成: 查询'{query[:50]}...'",
            payload={"results": [], "query": query},
            reply_to=msg.id,
        )

    @staticmethod
    def _classify_task(request: str) -> str:
        request_lower = request.lower()
        if any(kw in request_lower for kw in ["修复", "fix", "bug"]):
            return "bug_fix"
        if any(kw in request_lower for kw in ["开发", "feature", "功能", "新增"]):
            return "feature"
        if any(kw in request_lower for kw in ["审查", "review"]):
            return "review"
        if any(kw in request_lower for kw in ["部署", "deploy", "构建", "build"]):
            return "deploy"
        if any(kw in request_lower for kw in ["图片", "image", "图表", "chart"]):
            return "image_gen"
        return "general"
