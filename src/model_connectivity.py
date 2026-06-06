"""Lightweight model connectivity probes for office-scoped departments."""

from __future__ import annotations

import asyncio
import base64
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.image_generation import generate_doubao_image, is_image_generation_config
from src.llm.providers import LLMFactory, LLMMessage, ModelConfig


AGENT_IDS = ["zhongshu", "menxia", "shangshu", "libu", "hubu", "libu_comm", "bingbu", "xingbu", "gongbu"]

SAMPLE_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKUlEQVR4nO3NsQkAAA"
    "gDsP7/rwhOXuEgBLIn1XMqAoFAIBAIBAKB4EuwlqOYpoTPL+8AAAAASUVORK5CYII="
)


async def probe_model_connectivity(
    agent: str,
    office_id: str,
    config: ModelConfig,
    output_dir: Path | str = Path("output/model_tests/web"),
) -> dict[str, Any]:
    """Probe one configured department without running an office workflow."""
    kind = _probe_kind(config)
    result = {
        "office_id": office_id,
        "agent": agent,
        "provider": config.provider,
        "model": config.model,
        "kind": kind,
        "has_key": bool(config.api_key),
        "status": "not_run",
        "detail": "",
    }

    if not config.api_key and config.provider != "ollama":
        result["status"] = "missing_key"
        result["detail"] = "api_key is empty"
        return result

    try:
        if kind == "image":
            status, detail = await asyncio.to_thread(_image_probe, config, Path(output_dir), agent)
        elif kind == "vision":
            status, detail = await _vision_probe(config)
        else:
            status, detail = await _chat_probe(config)
    except asyncio.TimeoutError:
        status, detail = "timeout", "provider did not respond before timeout"
    except Exception as exc:
        status, detail = "error", f"{type(exc).__name__}: {exc}"

    result["status"] = status
    result["detail"] = _redact(detail)
    return result


async def _chat_probe(config: ModelConfig) -> tuple[str, str]:
    provider = LLMFactory.create(replace(config, max_tokens=16, temperature=0))
    response = await asyncio.wait_for(
        provider.chat([
            LLMMessage(role="system", content="Reply with exactly: pong"),
            LLMMessage(role="user", content="ping"),
        ]),
        timeout=45,
    )
    content = (response.content or "").strip()
    if _is_api_error(content):
        return "api_error", content[:400]
    return ("ok", content[:120]) if content else ("empty_response", "provider returned no text")


async def _vision_probe(config: ModelConfig) -> tuple[str, str]:
    provider = LLMFactory.create(replace(config, max_tokens=80, temperature=0))
    response = await asyncio.wait_for(
        provider.chat_with_vision(
            text="Connectivity test. Briefly describe whether this image is readable.",
            images=[SAMPLE_PNG_BASE64],
            system="You are checking whether a vision model API key and model can read one image.",
        ),
        timeout=75,
    )
    content = (response.content or "").strip()
    if _is_api_error(content):
        return "api_error", content[:400]
    return ("ok", content[:160]) if content else ("empty_response", "provider returned no text")


def _image_probe(config: ModelConfig, output_dir: Path, agent: str) -> tuple[str, str]:
    image = generate_doubao_image(
        config,
        "Connectivity test image, clean storyboard frame, one simple blue cube on a white table.",
        output_dir,
        f"{agent}_connectivity_probe",
        timeout_seconds=90,
    )
    path = Path(image.path)
    return "ok", f"generated {path.name}, {path.stat().st_size} bytes"


def _probe_kind(config: ModelConfig) -> str:
    model = (config.model or "").lower()
    if is_image_generation_config(config):
        return "image"
    if "vl" in model or "vision" in model:
        return "vision"
    return "chat"


def _is_api_error(content: str) -> bool:
    return content.startswith("[API") or "api key" in content.lower() and "incorrect" in content.lower()


def _redact(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(sk-[A-Za-z0-9_\-]{6})[A-Za-z0-9_\-]+", r"\1***", text)
    text = re.sub(r"(AKLT[A-Za-z0-9_\-]{6})[A-Za-z0-9_\-]+", r"\1***", text)
    return text[:500]
