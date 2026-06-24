"""Agent 基类 — 统一的消息收发接口和多模型 LLM 调用封装 (LiteLLM)"""

from __future__ import annotations

import json
import sys
import re
import dataclasses
from abc import ABC, abstractmethod
from typing import Optional

from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
    MessageMetadata,
)
from src.core.message_bus import message_bus
from src.llm.providers import (
    BaseLLMProvider,
    LLMMessage,
    LLMFactory,
)
from src.config_manager import config_manager


# 每个 agent 的标识 → config_manager 中的 key
AGENT_CONFIG_KEY = {
    AgentId.ZHONGSHU: "zhongshu",
    AgentId.MENXIA: "menxia",
    AgentId.SHANGSHU: "shangshu",
    AgentId.LIBU: "libu",
    AgentId.BINGBU: "bingbu",
    AgentId.XINGBU: "xingbu",
    AgentId.HUBU: "hubu",
    AgentId.LIBU_COMM: "libu_comm",
    AgentId.GONGBU: "gongbu",
}


class BaseAgent(ABC):
    """所有 Agent 的基类 — 使用可配置的多模型适配"""

    agent_id: AgentId

    def __init__(self, office_id: str = ""):
        if not self.agent_id:
            raise ValueError(f"{self.__class__.__name__} 必须定义 agent_id")
        self.office_id = office_id

    # ---- 子类必须实现 ----

    @property
    def system_prompt(self) -> str:
        """返回此 Agent 的系统提示词 (优先使用用户自定义)"""
        config_key = AGENT_CONFIG_KEY.get(self.agent_id, self.agent_id.value)
        return config_manager.get_prompt(config_key)

    # ---- LLM 调用 (多模型适配) ----

    @property
    def provider(self) -> BaseLLMProvider:
        """懒加载 LLM provider (根据配置自动选择模型)"""
        config_key = AGENT_CONFIG_KEY.get(self.agent_id, self.agent_id.value)
        model_config = config_manager.get_model_config(config_key, office_id=self.office_id)
        return LLMFactory.create(model_config)

    async def call_llm(
        self,
        prompt: str,
        output_schema: type = None,
        temperature: float = None,
        max_tokens: int = None,
        tool_names: list[str] = None,
    ) -> dict:
        """
        调用 LLM (通过 LiteLLM 自适应不同 provider), 支持 tool-use 多轮循环

        参数:
            prompt: 用户消息
            output_schema: 可选的 dataclass 类型, 用于结构化输出
            tool_names: 可用的工具名称列表 (从 tool_registry 获取), agent 可调用这些工具
        返回:
            dict — 如果指定了 output_schema 则返回结构化数据, 否则返回 {"content": str}
        """
        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=prompt),
        ]

        # 临时覆盖 temperature / max_tokens
        if temperature is not None:
            self.provider.config.temperature = temperature
        if max_tokens is not None:
            self.provider.config.max_tokens = max_tokens

        # 构建工具列表
        tools = []
        if output_schema:
            schema = self._schema_to_json(output_schema)
            tools.append({
                "type": "function",
                "function": {
                    "name": "output",
                    "description": f"输出结构化的 {output_schema.__name__}",
                    "parameters": schema,
                },
            })

        # 添加真实工具 (web_search, web_fetch, ...)
        if tool_names:
            from src.tools import tool_registry
            tool_defs = tool_registry.get_definitions(tool_names)
            tools.extend(tool_defs)

        tool_choice = None
        if output_schema and not tool_names:
            tool_choice = {"type": "function", "function": {"name": "output"}}

        # ---- Tool-use 循环 ----
        max_tool_rounds = 4
        search_count = 0
        for _round in range(max_tool_rounds):
            # 搜索过多时提醒 LLM 输出
            if search_count >= 6 and output_schema:
                messages.append(LLMMessage(role="user", content="已收集足够数据。请调用 output 输出最终结果，禁止继续搜索。"))
                tool_choice = {"type": "function", "function": {"name": "output"}}
            elif search_count >= 4 and output_schema:
                messages.append(LLMMessage(role="user", content="信息已较为充分，请调用 output 输出结果。"))

            response = await self.provider.chat(
                messages=messages,
                tools=tools if tools else None,
                tool_choice=tool_choice if not output_schema or _round < max_tool_rounds - 1 else None,
            )

            # 有 tool_calls?
            if response.tool_calls:
                try:
                    # 按顺序执行工具调用
                    tool_results = []
                    for tc in response.tool_calls:
                        name = tc.get("name", "")
                        args = tc.get("arguments", {})

                        if name == "output":
                            return args if args else {}

                        # 执行真实工具
                        from src.tools import tool_registry
                        tr = await tool_registry.execute(name, args)
                        tool_results.append({"call": tc, "result": tr})
                        if name in ("web_search", "web_fetch"):
                            search_count += 1
                        res_str = str(tr.get('result', tr.get('error', '')))
                        print(f"  [{self.agent_id.value}] [tool] {name}(#{search_count}) → {res_str[:100]}", file=sys.stderr)

                    # 将 assistant 的 tool_call 消息加入
                    tool_calls_for_msg = [
                        {"id": tc.get("id", f"call_{i}"), "type": "function",
                         "function": {"name": tc["name"], "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False)}}
                        for i, tc in enumerate(response.tool_calls)
                    ]
                    messages.append(LLMMessage(
                        role="assistant",
                        content=response.content or "",
                        tool_calls=tool_calls_for_msg,
                    ))

                    # 每个 tool 结果作为 tool 消息加入
                    for tr in tool_results:
                        tc = tr["call"]
                        call_id = tc.get("id", f"call_{tool_results.index(tr)}")
                        result_json = json.dumps(tr["result"], ensure_ascii=False, indent=2)
                        messages.append(LLMMessage(
                            role="tool",
                            content=result_json[:2500],
                            tool_call_id=call_id,
                        ))

                    continue  # 继续循环,让 LLM 处理工具结果

                except Exception as e:
                    print(f"  [{self.agent_id.value}] ⚠️ 工具执行异常: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc()
                    # 将错误作为普通文本返回
                    return {"content": f"(工具调用失败: {e})", "tokens_used": 0}

            # 没有 tool_calls — 处理文本响应
            content = response.content or ""

            # --- 结构化输出路径 (没有 tool_calls) ---
            if output_schema:
                if content:
                    json_obj = self._extract_json(content)
                    if json_obj:
                        return json_obj
                    if content.startswith("[API错误]"):
                        print(f"  [{self.agent_id.value}] LLM API 错误: {content}", file=sys.stderr)
                print(f"  [{self.agent_id.value}] ⚠️ 结构化输出失败, 返回空结果", file=sys.stderr)
                return {}

            # --- 纯文本路径 ---
            return {"content": content, "tokens_used": response.tokens_used}

        # 超过最大循环数
        print(f"  [{self.agent_id.value}] ⚠️ 工具调用超过{max_tool_rounds}轮, 强制返回", file=sys.stderr)
        return {"content": "(工具调用超限)", "tokens_used": 0}

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从文本中提取 JSON 对象"""
        if not text:
            return None
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试提取 ```json ... ``` 代码块
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试找到最外层 { }
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return None

    async def call_llm_with_vision(
        self,
        text: str,
        images: list[str] = None,
        system: str = "",
    ) -> dict:
        """多模态 LLM 调用 — 图片/视频输入支持"""
        response = await self.provider.chat_with_vision(
            text=text,
            images=images or [],
            system=system or self.system_prompt,
        )
        return {"content": response.content, "tokens_used": response.tokens_used}

    # ---- 消息收发 ----

    def register(self) -> None:
        message_bus.register(self.agent_id)

    async def send_message(
        self,
        to_agent: AgentId,
        msg_type: MessageType,
        payload: dict,
        task_id: str,
        context_refs: list[str] = None,
        parent_msg_id: str = None,
        confidence: float = 1.0,
    ) -> AgentMessage:
        """发送消息"""
        msg = message_bus.create_message(
            task_id=task_id,
            from_agent=self.agent_id,
            to_agent=to_agent,
            msg_type=msg_type,
            payload=payload,
            context_refs=context_refs,
            parent_msg_id=parent_msg_id,
            confidence=confidence,
        )
        await message_bus.send(msg)
        return msg

    async def receive_message(self, timeout: float = 300.0) -> AgentMessage:
        return await message_bus.receive(self.agent_id, timeout=timeout)

    async def receive_message_nowait(self) -> Optional[AgentMessage]:
        return await message_bus.receive_nowait(self.agent_id)

    async def start(self) -> None:
        self.register()

    async def stop(self) -> None:
        message_bus.unregister(self.agent_id)

    # ---- 辅助 ----

    @staticmethod
    def _schema_to_json(schema_type: type) -> dict:
        """dataclass → JSON Schema (支持嵌套 dataclass、list[X]、Optional[X])"""
        try:
            fields = dataclasses.fields(schema_type)
        except TypeError:
            return {"type": "object", "properties": {}}

        # 用 get_type_hints 解析 PEP 563 的字符串注解
        import typing
        try:
            resolved_types = typing.get_type_hints(schema_type)
        except Exception:
            resolved_types = {}

        properties = {}
        required = []

        for f in fields:
            real_type = resolved_types.get(f.name, f.type)
            field_schema, is_optional = BaseAgent._type_to_schema(real_type)
            properties[f.name] = field_schema

            if (not is_optional
                    and f.default is dataclasses.MISSING
                    and f.default_factory is dataclasses.MISSING):
                required.append(f.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    @staticmethod
    def _type_to_schema(python_type) -> tuple:
        """Python 类型 → (JSON Schema dict, is_optional: bool)"""
        import typing

        # 处理字符串注解 (PEP 563)
        if isinstance(python_type, str):
            return {"type": "string"}, False

        origin = typing.get_origin(python_type)
        args = typing.get_args(python_type)

        # Optional[X] = Union[X, None]
        if origin is typing.Union:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                schema, _ = BaseAgent._type_to_schema(non_none[0])
                return schema, True
            return {"type": "string"}, False

        # list[X]
        if origin is list:
            if args:
                item_schema, _ = BaseAgent._type_to_schema(args[0])
            else:
                item_schema = {"type": "string"}
            return {"type": "array", "items": item_schema}, False

        # dict
        if origin is dict:
            return {"type": "object", "properties": {}}, False

        # 嵌套 dataclass
        if dataclasses.is_dataclass(python_type):
            return BaseAgent._schema_to_json(python_type), False

        # 基本类型
        type_map = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}
        type_name = python_type.__name__ if hasattr(python_type, '__name__') else str(python_type)
        return {"type": type_map.get(type_name, "string")}, False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.agent_id.value})>"
