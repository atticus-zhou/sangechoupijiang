"""配置加载器 — 从 YAML/ENV 加载配置

简化版: 只做加载，不做 Web UI 持久化。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    """单个 Agent 的配置"""
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    system_prompt_override: str = ""  # 用户自定义提示词 (为空则用默认)


@dataclass
class CourtConfig:
    """朝堂配置"""
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    max_debate_rounds: int = 5           # 中书-门下最大辩论轮次
    max_step_retries: int = 3            # 兵部-刑部最大重试
    vector_db_path: str = "./data/chroma"
    similarity_threshold: float = 0.7

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "CourtConfig":
        """从 YAML 文件加载配置"""
        import yaml

        if not Path(path).exists():
            return cls._with_defaults()

        raw = Path(path).read_text(encoding="utf-8")
        raw = cls._expand_env(raw)
        data = yaml.safe_load(raw) or {}

        agents = {}
        models = data.get("models", {})
        for agent_id, cfg in models.items():
            agents[agent_id] = AgentConfig(
                provider=cfg.get("provider", "anthropic"),
                model=cfg.get("model", "claude-sonnet-4-6"),
                api_key=cfg.get("api_key", ""),
                api_base=cfg.get("api_base", ""),
                temperature=cfg.get("temperature", 0.3),
                max_tokens=cfg.get("max_tokens", 4096),
                system_prompt_override=cfg.get("system_prompt", ""),
            )

        system = data.get("system", {})
        return cls(
            agents=agents,
            max_debate_rounds=system.get("max_debate_rounds", 5),
            max_step_retries=system.get("max_step_retries", 3),
            vector_db_path=system.get("vector_db_path", "./data/chroma"),
            similarity_threshold=system.get("similarity_threshold", 0.7),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "CourtConfig":
        """从字典加载 (适合代码内配置)"""
        agents = {}
        for agent_id, cfg in data.get("models", {}).items():
            agents[agent_id] = AgentConfig(**cfg)

        system = data.get("system", {})
        return cls(
            agents=agents,
            max_debate_rounds=system.get("max_debate_rounds", 5),
            max_step_retries=system.get("max_step_retries", 3),
            vector_db_path=system.get("vector_db_path", "./data/chroma"),
            similarity_threshold=system.get("similarity_threshold", 0.7),
        )

    def get_agent_config(self, agent_id: str) -> AgentConfig:
        """获取某个 Agent 的配置，如果未配置则返回默认"""
        if agent_id in self.agents:
            return self.agents[agent_id]
        return AgentConfig()

    @staticmethod
    def _with_defaults() -> "CourtConfig":
        return CourtConfig(agents={
            "zhongshu": AgentConfig(provider="anthropic", model="claude-sonnet-4-6"),
            "menxia": AgentConfig(provider="anthropic", model="claude-sonnet-4-6"),
            "shangshu": AgentConfig(provider="anthropic", model="claude-sonnet-4-6"),
            "libu": AgentConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
            "bingbu": AgentConfig(provider="anthropic", model="claude-sonnet-4-6", max_tokens=8192),
            "xingbu": AgentConfig(provider="anthropic", model="claude-sonnet-4-6"),
        })

    @staticmethod
    def _expand_env(text: str) -> str:
        def replacer(match):
            var = match.group(1) or match.group(2)
            return os.getenv(var, match.group(0))
        return re.sub(r'\$\{(\w+)\}|\$(\w+)', replacer, text)
