"""LLM 多模型适配层 — 统一接口，通过 LiteLLM 支持 Claude / OpenAI / Ollama / 多模态

用户配置示例:
  models:
    zhongshu:
      provider: anthropic     # litellm 识别的 provider
      model: claude-sonnet-4-6
      api_key: ${ANTHROPIC_API_KEY}
    bingbu:
      provider: openai
      model: gpt-4o
      api_key: ${OPENAI_API_KEY}
    xingbu:
      provider: ollama
      model: llama3.1
      api_base: http://localhost:11434
"""

from __future__ import annotations

import json
import os
import sys
import asyncio
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import litellm

# 关闭 litellm 的详细日志
litellm.set_verbose = False
litellm.suppress_debug_info = True

# 调试开关 — 通过环境变量 LLM_DEBUG=1 开启
LLM_DEBUG = os.getenv("LLM_DEBUG", "").lower() in ("1", "true", "yes")


@dataclass
class ModelConfig:
    """单个模型配置"""
    provider: str = "deepseek"        # deepseek | anthropic | openai | ollama | gemini | ...
    model: str = "deepseek-chat"
    api_key: str = ""
    api_base: str = ""                # Ollama / 自定义端点
    temperature: float = 0.3
    max_tokens: int = 4096
    extra: dict = field(default_factory=dict)  # 额外参数

    def to_litellm_kwargs(self) -> dict:
        kwargs = {
            "model": f"{self.provider}/{self.model}",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.extra:
            kwargs.update(self.extra)
        return kwargs


@dataclass
class LLMResponse:
    """统一的 LLM 响应"""
    content: str
    model: str = ""
    tokens_used: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class LLMMessage:
    """统一的消息格式"""
    role: str          # "system" | "user" | "assistant" | "tool"
    content: str | list[dict]  # 纯文本 或 多模态内容列表
    tool_call_id: str = ""
    name: str = ""
    tool_calls: list[dict] = None  # assistant 的 tool_calls


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict] = None,
        tool_choice: str | dict = None,
        response_format: dict = None,
    ) -> LLMResponse:
        ...


class LiteLLMProvider(BaseLLMProvider):
    """基于 LiteLLM 的统一适配器"""

    def __init__(self, config: ModelConfig):
        self.config = config

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict] = None,
        tool_choice: str | dict = None,
        response_format: dict = None,
    ) -> LLMResponse:
        """调用 LiteLLM 的异步接口 (支持多模型自动适配)"""

        # 构建 litellm 消息格式
        litellm_messages = []
        for msg in messages:
            m = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = msg.name
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            litellm_messages.append(m)

        kwargs = self.config.to_litellm_kwargs()
        kwargs["messages"] = litellm_messages

        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if response_format:
            kwargs["response_format"] = response_format

        if LLM_DEBUG:
            model = kwargs.get("model", "?")
            msg_preview = str(litellm_messages[-1].get("content", ""))[:120] if litellm_messages else ""
            print(f"  [LLM] → {model} ({len(litellm_messages)} msgs, "
                  f"tools={'Y' if tools else 'N'}, tc={'Y' if tool_choice else 'N'}) "
                  f"prompt: {msg_preview}...", file=sys.stderr)

        try:
            # 在线程池中运行同步 litellm
            response = await asyncio.to_thread(litellm.completion, **kwargs)
        except Exception as e:
            print(f"  [LLM] ✗ API 调用失败: {e}", file=sys.stderr)
            if LLM_DEBUG:
                traceback.print_exc()
            # 返回空结果而不是抛异常, 让上层 agent 处理
            return LLMResponse(
                content=f"[API错误] {e}",
                model=kwargs.get("model", "unknown"),
                tokens_used=0,
            )

        choice = response.choices[0]
        msg = choice.message

        if LLM_DEBUG:
            content_len = len(msg.content or "")
            tc_count = len(msg.tool_calls or [])
            tokens = response.usage.total_tokens if response.usage else 0
            print(f"  [LLM] ← tokens={tokens} content_len={content_len} tool_calls={tc_count}", file=sys.stderr)

        result = LLMResponse(
            content=msg.content or "",
            model=response.model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )

        # 提取 tool_calls
        if msg.tool_calls:
            parsed_calls = []
            for tc in msg.tool_calls:
                args = {}
                if tc.function.arguments:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        # DeepSeek 偶尔生成含非法转义字符的 JSON
                        import re
                        fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', tc.function.arguments)
                        try:
                            args = json.loads(fixed)
                        except json.JSONDecodeError:
                            if LLM_DEBUG:
                                print(f"  [LLM] ⚠️ 无法解析 tool_call arguments: {tc.function.arguments[:200]}", file=sys.stderr)
                            args = {"_raw": tc.function.arguments}
                parsed_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })
            result.tool_calls = parsed_calls

        return result

    async def chat_with_vision(
        self,
        text: str,
        images: list[str] = None,  # base64 encoded images or URLs
        system: str = "",
        tools: list[dict] = None,
    ) -> LLMResponse:
        """多模态调用 — 支持图片/视频输入"""

        content = []

        if images:
            for img in images:
                # 判断是 URL 还是 base64
                if img.startswith("http://") or img.startswith("https://") or img.startswith("data:"):
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": img},
                    })
                else:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img}"},
                    })

        content.append({"type": "text", "text": text})

        messages = []
        if system:
            messages.append(LLMMessage(role="system", content=system))
        messages.append(LLMMessage(role="user", content=content))

        return await self.chat(messages, tools=tools)

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict] = None,
    ):
        """流式调用 — 生成器"""
        litellm_messages = []
        for msg in messages:
            m = {"role": msg.role, "content": msg.content}
            litellm_messages.append(m)

        kwargs = self.config.to_litellm_kwargs()
        kwargs["messages"] = litellm_messages
        kwargs["stream"] = True
        if tools:
            kwargs["tools"] = tools

        response = await asyncio.to_thread(litellm.completion, **kwargs)

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class LLMFactory:
    """LLM Provider 工厂"""

    @staticmethod
    def create(config: ModelConfig) -> BaseLLMProvider:
        return LiteLLMProvider(config)

    @staticmethod
    def create_from_dict(d: dict) -> BaseLLMProvider:
        config = ModelConfig(
            provider=d.get("provider", "deepseek"),
            model=d.get("model", "deepseek-chat"),
            api_key=d.get("api_key", ""),
            api_base=d.get("api_base", ""),
            temperature=d.get("temperature", 0.3),
            max_tokens=d.get("max_tokens", 4096),
            extra=d.get("extra", {}),
        )
        return LiteLLMProvider(config)


# 使用示例
def _example():
    """示例: 用户如何在配置中指定不同模型"""
    configs = {
        "zhongshu": ModelConfig(provider="anthropic", model="claude-sonnet-4-6"),
        "bingbu": ModelConfig(provider="openai", model="gpt-4o"),
        "xingbu": ModelConfig(provider="ollama", model="llama3.1", api_base="http://localhost:11434"),
    }
    providers = {name: LLMFactory.create(cfg) for name, cfg in configs.items()}
    return providers
