"""户部 — Resource & Data Agent: 文件管理、数据库操作、外部 API 调用"""

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
)
from src.data.prompts import HUBU_SYSTEM_PROMPT


class HubuAgent(BaseAgent):
    agent_id = AgentId.HUBU

    @property
    def system_prompt(self) -> str:
        return HUBU_SYSTEM_PROMPT

    async def read_file(self, path: str, task_id: str = "") -> dict:
        """读取文件或执行数据收集任务 — 可用 web_search/web_fetch"""
        prompt = f"""## 数据收集任务
任务描述: {path}

请根据以上描述收集和整理相关数据。**使用 web_search 和 web_fetch 获取真实数据，禁止编造。**
完成数据收集后，输出你的分析结果和收集到的信息。"""

        result = await self.call_llm(
            prompt=prompt, max_tokens=4096,
            tool_names=["web_search", "web_fetch"],
        )
        content = result.get("content", "")
        return {
            "action": "read",
            "target": path,
            "result": content or "(LLM 返回空, 数据收集失败)",
        }

    async def search_files(self, directory: str, pattern: str, task_id: str = "") -> dict:
        """搜索文件"""
        prompt = f"""## 搜索文件任务
目录: {directory}
搜索模式: {pattern}

请列出匹配的文件并描述每个文件的内容。"""

        result = await self.call_llm(prompt=prompt)
        return {
            "action": "search",
            "target": f"{directory}/{pattern}",
            "result": result.get("content", ""),
        }

    async def query_data(self, query: str, source: str = "", task_id: str = "") -> dict:
        """查询数据源"""
        prompt = f"""## 数据查询任务
查询: {query}
数据源: {source or "本地数据库"}

请执行此数据查询并返回结果。"""

        result = await self.call_llm(prompt=prompt)
        return {
            "action": "api_call",
            "target": source,
            "result": result.get("content", ""),
        }

    async def inventory(self, scope: str = "all", task_id: str = "") -> dict:
        """盘点可用资源"""
        prompt = f"""## 资源盘点
盘点范围: {scope}

请列出当前可用的资源:
1. 项目文件结构
2. 数据库表
3. 可用的外部 API
4. 配置文件"""

        result = await self.call_llm(prompt=prompt)
        return {
            "action": "inventory",
            "target": scope,
            "result": result.get("content", ""),
        }

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理资源操作请求"""
        action = msg.payload.get("action", "")

        if action == "read":
            result = await self.read_file(
                path=msg.payload.get("path", ""),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "read_result", "result": result},
            )

        elif action == "search":
            result = await self.search_files(
                directory=msg.payload.get("directory", "."),
                pattern=msg.payload.get("pattern", "*"),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "search_result", "result": result},
            )

        elif action == "query":
            result = await self.query_data(
                query=msg.payload.get("query", ""),
                source=msg.payload.get("source", ""),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "query_result", "result": result},
            )

        elif action == "inventory":
            result = await self.inventory(
                scope=msg.payload.get("scope", "all"),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "inventory_result", "result": result},
            )

        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
