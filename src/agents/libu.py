"""吏部 — Context Agent: 向量库管理"""

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
    VectorDocument,
    VectorMetadata,
)
from src.data.prompts import LIBU_SYSTEM_PROMPT
from src.storage.vector_store import vector_store


class LibuAgent(BaseAgent):
    agent_id = AgentId.LIBU

    # ---- 存储 ----

    async def store_document(
        self,
        content: str,
        doc_type: str,
        task_id: str,
        step_id: int = None,
        tags: list[str] = None,
        status: str = "draft",
        parent_ref: str = None,
    ) -> str:
        """写入文档到向量库"""
        doc = VectorDocument(
            id="",  # 自动生成
            content=content,
            metadata=VectorMetadata(
                doc_type=doc_type,
                task_id=task_id,
                agent=self.agent_id,
                step_id=step_id,
                tags=tags or [],
                status=status,
                parent_ref=parent_ref,
            ),
        )
        return vector_store.store(doc)

    async def store_plan(self, task_id: str, plan: dict) -> str:
        """存储 TaskPlan"""
        import json
        return await self.store_document(
            content=json.dumps(plan, ensure_ascii=False, indent=2),
            doc_type="task_plan",
            task_id=task_id,
            tags=["plan", f"v{plan.get('version', 1)}"],
            status="draft",
        )

    async def store_review(self, task_id: str, review: dict, plan_version: int) -> str:
        """存储 ReviewResult"""
        import json
        return await self.store_document(
            content=json.dumps(review, ensure_ascii=False, indent=2),
            doc_type="review_result",
            task_id=task_id,
            tags=["review", f"v{plan_version}", review.get("decision", "?")],
            status=review.get("decision", "?"),
        )

    async def store_agent_output(
        self, task_id: str, step_id: int, output: dict, agent: AgentId
    ) -> str:
        """存储 agent 产出并更新元数据中的 agent"""
        import json
        doc = VectorDocument(
            id="",
            content=json.dumps(output, ensure_ascii=False, indent=2),
            metadata=VectorMetadata(
                doc_type="agent_output",
                task_id=task_id,
                agent=agent,
                step_id=step_id,
                tags=["output", agent.value],
                status=output.get("status", "completed"),
            ),
        )
        return vector_store.store(doc)

    # ---- 检索 ----

    async def retrieve_context(self, query: str, task_id: str = None) -> list[dict]:
        """检索相关上下文"""
        filter_dict = None
        if task_id:
            filter_dict = {"task_id": task_id}

        docs = vector_store.retrieve(
            query=query,
            across_collections=["task_context", "code_knowledge", "task_history"],
            filter=filter_dict,
        )
        return [
            {
                "id": d.id,
                "content": d.content[:500],  # 截断,节省 token
                "score": d.score,
                "doc_type": d.metadata.doc_type,
                "tags": d.metadata.tags,
            }
            for d in docs
        ]

    async def get_task_documents(self, task_id: str) -> list[dict]:
        """获取任务最新文件"""
        return vector_store.get_latest_documents(task_id)

    async def query_history(self, task_description: str) -> list[dict]:
        """查询类似历史案例 (门下省用)"""
        docs = vector_store.retrieve(
            query=task_description,
            across_collections=["task_history"],
            top_k=5,
        )
        return [
            {
                "id": d.id,
                "content": d.content[:300],
                "score": d.score,
                "tags": d.metadata.tags,
            }
            for d in docs
        ]

    # ---- 归档 ----

    async def archive_task(self, task_id: str) -> str:
        """归档任务"""
        return vector_store.archive_task(task_id)

    # ---- 消息处理 ----

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理查询/存储请求"""
        action = msg.payload.get("action", "")

        if action == "retrieve":
            query = msg.payload.get("query", "")
            results = await self.retrieve_context(query, msg.task_id)
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "retrieve_result", "results": results},
            )

        elif action == "store_plan":
            doc_id = await self.store_plan(msg.task_id, msg.payload.get("plan", {}))
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "stored", "doc_id": doc_id},
                context_refs=[f"vec://task_context/{doc_id}"],
            )

        elif action == "query_history":
            results = await self.query_history(msg.payload.get("query", ""))
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "history_result", "results": results},
            )

        elif action == "get_latest_docs":
            docs = await self.get_task_documents(msg.task_id)
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "latest_docs", "documents": docs},
            )

        elif action == "archive":
            result = await self.archive_task(msg.task_id)
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "archived", "result": result},
            )

        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
