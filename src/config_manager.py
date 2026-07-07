"""用户配置管理 — YAML 文件 + SQLite 配置存储 + Web UI 可编辑

配置层级:
  1. config.yaml — 默认配置 (模型/提示词/工具)
  2. user_data/ — 用户自定义数据 (覆盖默认)
     ├─ prompts/    — 用户的 System Prompt (按部门)
     ├─ templates/  — 任务模板 (如 bug_fix.yaml)
     └─ tools/      — 自定义工具定义
  3. SQLite (user_data/config.db) — Web UI 编辑的配置持久化
"""

from __future__ import annotations

import os
import re
import yaml
import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from src.llm.providers import ModelConfig
from src.offices import get_office


# ============================================================
# 默认配置
# ============================================================

DEFAULT_CONFIG_YAML = """# ============================================================
# 三省六部 · 默认配置
# 用户可在 Web UI 中修改, 或直接编辑此文件
# ============================================================

# ---- 模型配置 (每个部门可独立选择模型) ----
models:
  zhongshu:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.7
    max_tokens: 4096

  menxia:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.2
    max_tokens: 4096

  shangshu:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.3
    max_tokens: 4096

  libu:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.1
    max_tokens: 2048

  hubu:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.2
    max_tokens: 4096

  libu_comm:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.3
    max_tokens: 2048

  bingbu:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.3
    max_tokens: 8192

  xingbu:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.2
    max_tokens: 4096

  gongbu:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    temperature: 0.5
    max_tokens: 8192

# ---- 系统设置 ----
system:
  max_zhongshu_menxia_rounds: 3
  max_bingbu_xingbu_retries: 2
  max_orchestrator_loops: 30
  vector_db_path: ./data/chroma
  similarity_threshold: 0.7

# ---- 任务模板 ----
templates:
  bug_fix:
    name: "Bug 修复"
    description: "定位并修复代码缺陷"
    default_prompt: "请修复以下 Bug: {user_input}"

  code_review:
    name: "代码审查"
    description: "对代码进行全面审查"
    default_prompt: "请审查以下代码的质量和安全性: {user_input}"

  new_feature:
    name: "新功能开发"
    description: "从零开发一个新功能"
    default_prompt: "请实现以下功能: {user_input}"

  performance:
    name: "性能优化"
    description: "分析和优化系统性能"
    default_prompt: "请分析并优化以下性能问题: {user_input}"
"""


# ============================================================
# 配置管理器
# ============================================================

@dataclass
class SystemConfig:
    max_zhongshu_menxia_rounds: int = 5
    max_bingbu_xingbu_retries: int = 3
    max_orchestrator_loops: int = 100
    vector_db_path: str = "./data/chroma"
    similarity_threshold: float = 0.7


class ConfigManager:
    """统一配置管理 — YAML + SQLite"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.config_path = self.base_dir / "config.yaml"
        self.user_data_dir = self.base_dir / "user_data"
        self.prompts_dir = self.user_data_dir / "prompts"
        self.templates_dir = self.user_data_dir / "templates"
        self.tools_dir = self.user_data_dir / "tools"
        self.db_path = self.user_data_dir / "config.db"

        self._ensure_dirs()
        self._ensure_default_config()
        self._ensure_db()

    def _ensure_dirs(self):
        for d in [self.user_data_dir, self.prompts_dir, self.templates_dir, self.tools_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _ensure_default_config(self):
        if not self.config_path.exists():
            self.config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")

    # ---- YAML 配置 ----

    def load_yaml(self) -> dict:
        """加载 config.yaml, 替换环境变量"""
        raw = self.config_path.read_text(encoding="utf-8")
        # ${VAR} → 环境变量
        raw = self._expand_env_vars(raw)
        return yaml.safe_load(raw) or {}

    def save_yaml(self, data: dict) -> None:
        """保存到 config.yaml (保留格式)"""
        content = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        self.config_path.write_text(content, encoding="utf-8")

    def get_model_config(self, agent: str, office_id: str = "") -> ModelConfig:
        """Get a department model config, optionally scoped to an office."""
        config = self.load_yaml()
        global_models = config.get("models", {})
        office_models = config.get("office_models", {})
        office_agent_config = {}
        if office_id:
            office_agent_config = (office_models.get(office_id, {}) or {}).get(agent, {}) or {}
        agent_config = {**(global_models.get(agent, {}) or {}), **office_agent_config}
        return ModelConfig(
            provider=str(agent_config.get("provider", "deepseek") or "").strip() or "deepseek",
            model=str(agent_config.get("model", "deepseek-chat") or "").strip() or "deepseek-chat",
            api_key=str(agent_config.get("api_key", "") or "").strip(),
            api_base=str(agent_config.get("api_base", "") or "").strip(),
            temperature=agent_config.get("temperature", 0.3),
            max_tokens=agent_config.get("max_tokens", 4096),
            extra=agent_config.get("extra", {}),
        )

    def get_system_config(self) -> SystemConfig:
        config = self.load_yaml()
        sys_config = config.get("system", {})
        return SystemConfig(
            max_zhongshu_menxia_rounds=sys_config.get("max_zhongshu_menxia_rounds", 5),
            max_bingbu_xingbu_retries=sys_config.get("max_bingbu_xingbu_retries", 3),
            max_orchestrator_loops=sys_config.get("max_orchestrator_loops", 100),
            vector_db_path=sys_config.get("vector_db_path", "./data/chroma"),
            similarity_threshold=sys_config.get("similarity_threshold", 0.7),
        )

    def get_templates(self) -> dict:
        config = self.load_yaml()
        return config.get("templates", {})

    # ---- 提示词管理 ----

    def get_prompt(self, agent: str) -> str:
        """获取某部门的 System Prompt — 优先用户自定义, 否则用默认"""
        # 1. 尝试从 user_data/prompts/ 读取
        user_prompt_path = self.prompts_dir / f"{agent}.txt"
        if user_prompt_path.exists():
            return user_prompt_path.read_text(encoding="utf-8")

        # 2. 返回默认 prompt
        from src.data.prompts import AGENT_PROMPTS
        return AGENT_PROMPTS.get(agent, "")

    def save_prompt(self, agent: str, text: str) -> None:
        """保存用户自定义的 System Prompt"""
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        (self.prompts_dir / f"{agent}.txt").write_text(text, encoding="utf-8")

    def list_custom_prompts(self) -> list[str]:
        """列出用户已自定义提示词的部门"""
        return [p.stem for p in self.prompts_dir.glob("*.txt")]

    def delete_prompt(self, agent: str) -> bool:
        """删除用户自定义提示词 (回退到默认)"""
        path = self.prompts_dir / f"{agent}.txt"
        if path.exists():
            path.unlink()
            return True
        return False

    # ---- 模板管理 ----

    def list_templates(self) -> list[dict]:
        """列出所有可用模板"""
        templates = []

        # YAML 中定义的模板
        yaml_templates = self.get_templates()
        for key, tpl in yaml_templates.items():
            templates.append({
                "id": key,
                "name": tpl.get("name", key),
                "description": tpl.get("description", ""),
                "source": "default",
            })

        # user_data/templates/ 中的模板
        for f in self.templates_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            templates.append({
                "id": f.stem,
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "source": "custom",
            })

        return templates

    def get_template(self, template_id: str) -> dict:
        """获取指定模板"""
        # 先从用户目录
        user_path = self.templates_dir / f"{template_id}.yaml"
        if user_path.exists():
            return yaml.safe_load(user_path.read_text(encoding="utf-8")) or {}

        # 再从 YAML 配置
        templates = self.get_templates()
        return templates.get(template_id, {"name": template_id})

    def save_template(self, template_id: str, data: dict) -> None:
        """保存用户模板"""
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        (self.templates_dir / f"{template_id}.yaml").write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )

    # ---- SQLite (Web UI 持久化) ----

    def _ensure_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config_store (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                task_id TEXT PRIMARY KEY,
                user_request TEXT,
                template_id TEXT,
                status TEXT,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_runs (
                task_id TEXT PRIMARY KEY,
                user_request TEXT,
                template_id TEXT,
                status TEXT,
                current_phase TEXT,
                error TEXT,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                event_type TEXT,
                status TEXT,
                summary TEXT,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                office_id TEXT,
                title TEXT,
                brief TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                workspace_id TEXT,
                task_id TEXT,
                artifact_type TEXT,
                title TEXT,
                uri TEXT,
                content TEXT,
                metadata TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def get_kv(self, key: str, default: str = "") -> str:
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT value FROM config_store WHERE key=?", (key,)).fetchone()
        conn.close()
        return row[0] if row else default

    def set_kv(self, key: str, value: str) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT OR REPLACE INTO config_store (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value),
        )
        conn.commit()
        conn.close()

    def save_task_record(self, task_id: str, user_request: str, template_id: str, status: str, result: dict) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT OR REPLACE INTO task_history (task_id, user_request, template_id, status, result) VALUES (?, ?, ?, ?, ?)",
            (task_id, user_request, template_id, status, json.dumps(result, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def create_task_run(self, task_id: str, user_request: str, template_id: str = "") -> None:
        """Create or reset the durable run record for a task."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            INSERT OR REPLACE INTO task_runs
                (task_id, user_request, template_id, status, current_phase, error, result, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, NULL)
            """,
            (task_id, user_request, template_id or "", "queued", "queued", "", ""),
        )
        conn.commit()
        conn.close()

    def update_task_run(
        self,
        task_id: str,
        status: str,
        current_phase: str = "",
        error: str = "",
        result: Optional[dict] = None,
        completed: bool = False,
    ) -> None:
        """Update durable task status without losing the original request."""
        result_text = json.dumps(result, ensure_ascii=False) if result is not None else None
        conn = sqlite3.connect(str(self.db_path))
        if result_text is None:
            conn.execute(
                """
                UPDATE task_runs
                SET status=?, current_phase=COALESCE(NULLIF(?, ''), current_phase),
                    error=?, updated_at=CURRENT_TIMESTAMP,
                    completed_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE task_id=?
                """,
                (status, current_phase, error, 1 if completed else 0, task_id),
            )
        else:
            conn.execute(
                """
                UPDATE task_runs
                SET status=?, current_phase=COALESCE(NULLIF(?, ''), current_phase),
                    error=?, result=?, updated_at=CURRENT_TIMESTAMP,
                    completed_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE task_id=?
                """,
                (status, current_phase, error, result_text, 1 if completed else 0, task_id),
            )
        conn.commit()
        conn.close()

    def mark_interrupted_task_runs(self, reason: str) -> int:
        """Mark durable in-memory background tasks as interrupted after process restart."""
        result = {"status": "interrupted", "error": reason}
        result_text = json.dumps(result, ensure_ascii=False)
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute(
            """
            SELECT task_id FROM task_runs
            WHERE status IN ('queued', 'running')
            """
        ).fetchall()
        changed = 0
        for (task_id,) in rows:
            conn.execute(
                """
                UPDATE task_runs
                SET status='interrupted',
                    current_phase='interrupted',
                    error=?,
                    result=?,
                    updated_at=CURRENT_TIMESTAMP,
                    completed_at=CURRENT_TIMESTAMP
                WHERE task_id=?
                """,
                (reason, result_text, task_id),
            )
            conn.execute(
                """
                INSERT INTO task_events (task_id, event_type, status, summary, payload)
                VALUES (?, 'task_interrupted_after_restart', 'interrupted', ?, ?)
                """,
                (
                    task_id,
                    reason,
                    json.dumps({"reason": reason}, ensure_ascii=False),
                ),
            )
            changed += 1
        conn.commit()
        conn.close()
        return changed

    def append_task_event(
        self,
        task_id: str,
        event_type: str,
        status: str,
        summary: str,
        payload: Optional[dict] = None,
    ) -> None:
        """Append an auditable task event."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            INSERT INTO task_events (task_id, event_type, status, summary, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, event_type, status, summary, json.dumps(payload or {}, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def get_task_run(self, task_id: str) -> dict:
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            """
            SELECT task_id, user_request, template_id, status, current_phase, error,
                   result, created_at, updated_at, completed_at
            FROM task_runs WHERE task_id=?
            """,
            (task_id,),
        ).fetchone()
        events = conn.execute(
            """
            SELECT event_type, status, summary, payload, created_at
            FROM task_events WHERE task_id=? ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()
        conn.close()
        if not row:
            return {}
        result = {}
        if row[6]:
            try:
                result = json.loads(row[6])
            except json.JSONDecodeError:
                result = {"raw": row[6]}
        return {
            "task_id": row[0],
            "user_request": row[1],
            "template_id": row[2],
            "status": row[3],
            "current_phase": row[4],
            "error": row[5],
            "result": result,
            "created_at": row[7],
            "updated_at": row[8],
            "completed_at": row[9],
            "events": [
                {
                    "event_type": e[0],
                    "status": e[1],
                    "summary": e[2],
                    "payload": json.loads(e[3] or "{}"),
                    "created_at": e[4],
                }
                for e in events
            ],
        }

    def list_workspace_task_runs(self, workspace_id: str, limit: int = 20) -> list[dict]:
        """List task runs that declared activity for a workspace."""
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute(
            """
            SELECT DISTINCT tr.task_id, tr.user_request, tr.status, tr.current_phase,
                   tr.error, tr.created_at, tr.updated_at, tr.completed_at
            FROM task_runs tr
            JOIN task_events te ON te.task_id = tr.task_id
            WHERE te.payload LIKE ?
            ORDER BY tr.updated_at DESC, tr.created_at DESC
            LIMIT ?
            """,
            (f'%"{workspace_id}"%', limit),
        ).fetchall()
        task_ids = [r[0] for r in rows]
        events_by_task: dict[str, list[dict]] = {task_id: [] for task_id in task_ids}
        if task_ids:
            placeholders = ",".join("?" for _ in task_ids)
            event_rows = conn.execute(
                f"""
                SELECT task_id, event_type, status, summary, payload, created_at
                FROM task_events
                WHERE task_id IN ({placeholders})
                ORDER BY id ASC
                """,
                task_ids,
            ).fetchall()
            for e in event_rows:
                try:
                    payload = json.loads(e[4] or "{}")
                except json.JSONDecodeError:
                    payload = {}
                events_by_task.setdefault(e[0], []).append({
                    "event_type": e[1],
                    "status": e[2],
                    "summary": e[3],
                    "payload": payload,
                    "created_at": e[5],
                })
        conn.close()
        return [
            {
                "task_id": r[0],
                "user_request": r[1],
                "status": r[2],
                "current_phase": r[3],
                "error": r[4],
                "created_at": r[5],
                "updated_at": r[6],
                "completed_at": r[7],
                "events": events_by_task.get(r[0], []),
            }
            for r in rows
        ]

    def create_workspace(
        self,
        workspace_id: str,
        office_id: str,
        title: str,
        brief: str = "",
        status: str = "active",
    ) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            INSERT OR REPLACE INTO workspaces
                (workspace_id, office_id, title, brief, status, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (workspace_id, office_id, title, brief, status),
        )
        conn.commit()
        conn.close()

    def list_workspaces(self, limit: int = 50, office_id: str = "") -> list[dict]:
        conn = sqlite3.connect(str(self.db_path))
        if office_id:
            rows = conn.execute(
                """
                SELECT workspace_id, office_id, title, brief, status, created_at, updated_at
                FROM workspaces WHERE office_id=?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (office_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT workspace_id, office_id, title, brief, status, created_at, updated_at
                FROM workspaces ORDER BY updated_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        conn.close()
        return [
            {
                "workspace_id": r[0],
                "office_id": r[1],
                "title": r[2],
                "brief": r[3],
                "status": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
            for r in rows
        ]

    def get_workspace(self, workspace_id: str) -> dict:
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            """
            SELECT workspace_id, office_id, title, brief, status, created_at, updated_at
            FROM workspaces WHERE workspace_id=?
            """,
            (workspace_id,),
        ).fetchone()
        conn.close()
        if not row:
            return {}
        return {
            "workspace_id": row[0],
            "office_id": row[1],
            "title": row[2],
            "brief": row[3],
            "status": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }

    def create_artifact(
        self,
        artifact_id: str,
        workspace_id: str,
        task_id: str,
        artifact_type: str,
        title: str,
        uri: str = "",
        content: str = "",
        metadata: Optional[dict] = None,
        created_by: str = "",
    ) -> None:
        metadata = self._normalize_artifact_metadata(
            artifact_id=artifact_id,
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type=artifact_type,
            title=title,
            metadata=metadata,
            created_by=created_by,
        )
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            INSERT OR REPLACE INTO artifacts
                (artifact_id, workspace_id, task_id, artifact_type, title, uri, content, metadata, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                workspace_id,
                task_id,
                artifact_type,
                title,
                uri,
                content,
                json.dumps(metadata, ensure_ascii=False),
                created_by,
            ),
        )
        conn.execute(
            "UPDATE workspaces SET updated_at=CURRENT_TIMESTAMP WHERE workspace_id=?",
            (workspace_id,),
        )
        conn.commit()
        conn.close()

    def _normalize_artifact_metadata(
        self,
        artifact_id: str,
        workspace_id: str,
        task_id: str,
        artifact_type: str,
        title: str,
        metadata: Optional[dict],
        created_by: str,
    ) -> dict:
        """Apply the office artifact contract before writing to SQLite."""
        if not str(artifact_id or "").strip():
            raise ValueError("artifact_id is required by the office artifact contract")
        if not str(artifact_type or "").strip():
            raise ValueError("artifact_type is required by the office artifact contract")
        if not str(title or "").strip():
            raise ValueError("title is required by the office artifact contract")

        normalized = dict(metadata or {})
        workspace = self.get_workspace(workspace_id) if workspace_id else {}
        office_id = str(normalized.get("office_id") or workspace.get("office_id") or "system").strip()
        office = get_office(office_id)
        contract = office.artifact_contract or {}
        required_metadata = contract.get("required_metadata") or [
            "office_id",
            "source",
            "version",
            "responsible_agent",
            "reference_chain",
        ]

        normalized.setdefault("office_id", office.id if office_id != "system" else "system")
        normalized.setdefault("source", f"workspace:{workspace_id}" if workspace_id else f"task:{task_id}")
        normalized.setdefault("version", "v1")
        normalized.setdefault("responsible_agent", created_by or "system")
        normalized.setdefault(
            "reference_chain",
            self._default_reference_chain(workspace_id=workspace_id, task_id=task_id),
        )

        missing = [field for field in required_metadata if field not in normalized or normalized[field] in ("", None, [])]
        if missing:
            raise ValueError(f"artifact metadata missing required contract fields: {', '.join(missing)}")
        if not isinstance(normalized.get("reference_chain"), list):
            raise ValueError("artifact metadata field reference_chain must be a list")
        return normalized

    def _default_reference_chain(self, workspace_id: str, task_id: str) -> list[dict]:
        chain = []
        if workspace_id:
            chain.append({"kind": "workspace", "id": workspace_id})
        if task_id:
            chain.append({"kind": "task", "id": task_id})
        return chain or [{"kind": "system", "id": "local"}]

    def list_artifacts(self, workspace_id: str = "", task_id: str = "") -> list[dict]:
        conn = sqlite3.connect(str(self.db_path))
        if workspace_id:
            rows = conn.execute(
                """
                SELECT artifact_id, workspace_id, task_id, artifact_type, title, uri,
                       content, metadata, created_by, created_at
                FROM artifacts WHERE workspace_id=? ORDER BY created_at ASC
                """,
                (workspace_id,),
            ).fetchall()
        elif task_id:
            rows = conn.execute(
                """
                SELECT artifact_id, workspace_id, task_id, artifact_type, title, uri,
                       content, metadata, created_by, created_at
                FROM artifacts WHERE task_id=? ORDER BY created_at ASC
                """,
                (task_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT artifact_id, workspace_id, task_id, artifact_type, title, uri,
                       content, metadata, created_by, created_at
                FROM artifacts ORDER BY created_at DESC LIMIT 100
                """
            ).fetchall()
        conn.close()
        return [
            {
                "artifact_id": r[0],
                "workspace_id": r[1],
                "task_id": r[2],
                "artifact_type": r[3],
                "title": r[4],
                "uri": r[5],
                "content": r[6],
                "metadata": json.loads(r[7] or "{}"),
                "created_by": r[8],
                "created_at": r[9],
            }
            for r in rows
        ]

    def get_artifact(self, artifact_id: str) -> dict:
        """Get one artifact by id."""
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            """
            SELECT artifact_id, workspace_id, task_id, artifact_type, title, uri,
                   content, metadata, created_by, created_at
            FROM artifacts WHERE artifact_id=?
            """,
            (artifact_id,),
        ).fetchone()
        conn.close()
        if not row:
            return {}
        return {
            "artifact_id": row[0],
            "workspace_id": row[1],
            "task_id": row[2],
            "artifact_type": row[3],
            "title": row[4],
            "uri": row[5],
            "content": row[6],
            "metadata": json.loads(row[7] or "{}"),
            "created_by": row[8],
            "created_at": row[9],
        }

    def delete_artifacts_for_task(self, task_id: str, preserve_evidence: bool = True) -> int:
        """Delete task report artifacts and optionally preserve evidence artifacts."""
        conn = sqlite3.connect(str(self.db_path))
        if preserve_evidence:
            cursor = conn.execute(
                """
                DELETE FROM artifacts
                WHERE task_id=?
                  AND artifact_type NOT IN ('screenshot_evidence', 'screenshot_extraction')
                """,
                (task_id,),
            )
        else:
            cursor = conn.execute("DELETE FROM artifacts WHERE task_id=?", (task_id,))
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count

    def get_task_history(self, limit: int = 20) -> list[dict]:
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute(
            "SELECT task_id, user_request, template_id, status, created_at FROM task_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {"task_id": r[0], "user_request": r[1], "template_id": r[2], "status": r[3], "created_at": r[4]}
            for r in rows
        ]

    def get_task_result(self, task_id: str) -> dict:
        """获取单个任务的完整结果（含 final_report）"""
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            "SELECT task_id, user_request, template_id, status, result, created_at FROM task_history WHERE task_id=?",
            (task_id,),
        ).fetchone()
        conn.close()
        if not row:
            return {}
        result = {}
        if row[4]:
            try:
                result = json.loads(row[4])
            except json.JSONDecodeError:
                result = {"raw": row[4]}
        return {
            "task_id": row[0],
            "user_request": row[1],
            "template_id": row[2],
            "status": row[3],
            "result": result,
            "created_at": row[5],
        }

    # ---- 辅助 ----

    @staticmethod
    def _expand_env_vars(text: str) -> str:
        """将 ${VAR} 或 $VAR 替换为环境变量值"""
        def replacer(match):
            var = match.group(1) or match.group(2)
            return os.getenv(var, match.group(0))
        return re.sub(r'\$\{(\w+)\}|\$(\w+)', replacer, text)


# 全局单例
config_manager = ConfigManager(base_dir=".")
