"""吏部 — 共享向量库封装 (ChromaDB)"""

from __future__ import annotations

import os
import uuid
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config.loader import CourtConfig as _CourtConfig
_config = _CourtConfig()

# VectorDocument / VectorMetadata 内联定义以避免循环依赖
from dataclasses import dataclass, field
from typing import Optional as _Optional

@dataclass
class VectorMetadata:
    doc_type: str = ""
    task_id: str = ""
    agent: str = ""
    step_id: _Optional[int] = None
    timestamp: str = ""
    tags: list = field(default_factory=list)
    status: str = "draft"
    parent_ref: _Optional[str] = None

@dataclass
class VectorDocument:
    id: str = ""
    content: str = ""
    metadata: VectorMetadata = field(default_factory=VectorMetadata)
    embedding: _Optional[list] = None
    score: float = 0.0


class VectorStore:
    """ChromaDB 封装 — 吏部的存储后端"""

    COLLECTIONS = {
        "task_context": "当前任务上下文",
        "code_knowledge": "代码知识库",
        "task_history": "历史案例库",
        "agent_memory": "Agent 间消息存档",
    }

    def __init__(self):
        db_path = _config.vector_db_path
        os.makedirs(db_path, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=db_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        """确保所有 collection 存在"""
        existing = {c.name if hasattr(c, 'name') else str(c) for c in self._client.list_collections()}
        for name in self.COLLECTIONS:
            if name not in existing:
                self._client.create_collection(name=name)

    # ---- CRUD ----

    def store(self, doc: VectorDocument, collection_name_override: str = None) -> str:
        """写入文档到向量库，返回 doc_id。可指定覆盖 collection"""
        if not doc.id:
            doc.id = str(uuid.uuid4())

        collection_name = collection_name_override or self._resolve_collection(doc.metadata.doc_type)
        collection = self._client.get_collection(name=collection_name)
        metadata_dict = self._metadata_to_dict(doc.metadata)

        collection.add(
            ids=[doc.id],
            documents=[doc.content],
            metadatas=[metadata_dict],
        )
        return doc.id

    def retrieve(
        self,
        query: str,
        across_collections: list[str] = None,
        top_k: int = 5,
        filter: dict = None,
    ) -> list[VectorDocument]:
        """跨 collection 语义检索"""
        if across_collections is None:
            across_collections = ["task_context", "code_knowledge", "task_history"]

        results: list[VectorDocument] = []

        for coll_name in across_collections:
            if coll_name not in self.COLLECTIONS:
                continue

            try:
                collection = self._client.get_collection(name=coll_name)
                query_result = collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=filter,
                )

                if query_result["ids"] and query_result["ids"][0]:
                    for i, doc_id in enumerate(query_result["ids"][0]):
                        doc_content = (
                            query_result["documents"][0][i]
                            if query_result["documents"] and query_result["documents"][0]
                            else ""
                        )
                        metadata = (
                            query_result["metadatas"][0][i]
                            if query_result["metadatas"] and query_result["metadatas"][0]
                            else {}
                        )
                        distance = (
                            query_result["distances"][0][i]
                            if query_result["distances"] and query_result["distances"][0]
                            else 0.0
                        )

                        results.append(VectorDocument(
                            id=doc_id,
                            content=doc_content,
                            metadata=self._dict_to_metadata(metadata),
                            score=1.0 - min(distance, 1.0),  # distance → similarity
                        ))
            except Exception:
                continue

        # 按相似度降序排列
        results.sort(key=lambda x: x.score, reverse=True)

        # 相似度过滤
        results = [r for r in results if r.score >= _config.similarity_threshold]

        return results[:top_k]

    def get_by_id(self, doc_id: str, collection: str) -> Optional[VectorDocument]:
        """按 ID 获取文档"""
        try:
            coll = self._client.get_collection(name=collection)
            result = coll.get(ids=[doc_id])
            if result["ids"]:
                return VectorDocument(
                    id=result["ids"][0],
                    content=result["documents"][0] if result.get("documents") and result["documents"] else "",
                    metadata=self._dict_to_metadata(
                        result["metadatas"][0] if result.get("metadatas") and result["metadatas"] else {}
                    ),
                )
        except Exception:
            pass
        return None

    def delete_by_task(self, task_id: str, collection: str) -> int:
        """删除某任务在指定 collection 中的所有文档"""
        try:
            coll = self._client.get_collection(name=collection)
            # ChromaDB 没有原生 delete by filter，需先查后删
            result = coll.get(where={"task_id": task_id})
            if result["ids"]:
                coll.delete(ids=result["ids"])
                return len(result["ids"])
        except Exception:
            pass
        return 0

    # ---- 吏部专用接口 ----

    def get_task_context(self, task_id: str) -> dict:
        """获取当前任务的全部上下文摘要"""
        context_docs = self.retrieve(
            query="",
            across_collections=["task_context", "agent_memory"],
            filter={"task_id": task_id},
            top_k=50,
        )

        # 按类型分组
        grouped: dict[str, list[VectorDocument]] = {}
        for doc in context_docs:
            doc_type = doc.metadata.doc_type
            grouped.setdefault(doc_type, []).append(doc)

        return {
            "task_id": task_id,
            "total_docs": len(context_docs),
            "by_type": {
                k: [{"id": d.id, "summary": d.content[:200], "score": d.score} for d in v]
                for k, v in grouped.items()
            },
            "all_docs": context_docs,
        }

    def get_latest_documents(self, task_id: str) -> list[dict]:
        """获取某任务的最新文件 (朝堂报告用)"""
        docs = self.retrieve(
            query="",
            across_collections=["task_context"],
            filter={"task_id": task_id},
            top_k=10,
        )

        result = []
        for doc in docs:
            result.append({
                "doc_type": doc.metadata.doc_type,
                "version": doc.metadata.tags,
                "status": doc.metadata.status,
                "content": doc.content,
                "agent": doc.metadata.agent.value if isinstance(doc.metadata.agent, type) else str(doc.metadata.agent),
            })
        return result

    def archive_task(self, task_id: str) -> str:
        """归档任务: 从 task_context → task_history"""
        # 获取所有 task_context 文档
        docs = self.retrieve(
            query="",
            across_collections=["task_context"],
            filter={"task_id": task_id},
            top_k=100,
        )

        if not docs:
            return f"无文档需要归档 (task_id={task_id})"

        # 提取标签 (基于 doc_type 统计)
        tag_counts: dict[str, int] = {}
        for doc in docs:
            tag_counts[doc.metadata.doc_type] = tag_counts.get(doc.metadata.doc_type, 0) + 1
        tags = list(tag_counts.keys())

        # 复制到 task_history
        for doc in docs:
            doc.metadata.tags = tags
            doc.metadata.status = "archived"
            doc.id = f"history_{doc.id}"
            self.store(doc, collection_name_override="task_history")

        # 清理 task_context
        self.delete_by_task(task_id, "task_context")

        return f"归档完成: {len(docs)} 条文档, 标签: {tags}"

    # ---- 辅助 ----

    @staticmethod
    def _resolve_collection(doc_type: str) -> str:
        mapping = {
            "task_plan": "task_context",
            "review_result": "task_context",
            "agent_output": "task_context",
            "agent_message": "agent_memory",
            "court_event": "agent_memory",
            "code_snippet": "code_knowledge",
            "case_study": "task_history",
        }
        return mapping.get(doc_type, "task_context")

    @staticmethod
    def _metadata_to_dict(meta: VectorMetadata) -> dict:
        return {
            "doc_type": meta.doc_type,
            "task_id": meta.task_id,
            "agent": meta.agent.value if isinstance(meta.agent, type) else str(meta.agent),
            "step_id": meta.step_id,
            "timestamp": meta.timestamp,
            "tags": ",".join(meta.tags),
            "status": meta.status,
            "parent_ref": meta.parent_ref or "",
        }

    @staticmethod
    def _dict_to_metadata(d: dict) -> VectorMetadata:
        agent_raw = d.get("agent", "吏部")

        tags_raw = d.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        step_id = d.get("step_id")
        if step_id:
            try:
                step_id = int(step_id)
            except (TypeError, ValueError):
                step_id = None

        return VectorMetadata(
            doc_type=d.get("doc_type", ""),
            task_id=d.get("task_id", ""),
            agent=agent_raw,
            step_id=step_id,
            timestamp=d.get("timestamp", ""),
            tags=tags,
            status=d.get("status", "draft"),
            parent_ref=d.get("parent_ref") or None,
        )


# 全局单例
vector_store = VectorStore()
