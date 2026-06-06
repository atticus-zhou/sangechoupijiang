"""Image generation providers for visual offices.

This module is intentionally separate from ``src.llm.providers``. Image models
such as Seedream do not behave like chat-completion models, and keeping them in
their own adapter prevents office/model configuration collisions.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.llm.providers import ModelConfig


DEFAULT_ARK_IMAGE_BASE = "https://ark.cn-beijing.volces.com/api/v3"

DOUBAO_IMAGE_MODEL_ALIASES = {
    "doubao-seedream-5": "doubao-seedream-5-0-260128",
    "doubao-seedream-5-0": "doubao-seedream-5-0-260128",
    "doubao-seedream-5.0-lite": "doubao-seedream-5-0-260128",
    "doubao-seedream-4-5": "doubao-seedream-4-5-251128",
    "doubao-seedream-4-0": "doubao-seedream-4-0-250828",
}


@dataclass
class GeneratedImage:
    title: str
    prompt: str
    path: str
    provider: str
    model: str
    source_url: str = ""
    size: str = ""
    metadata: dict[str, Any] | None = None


class ImageGenerationError(RuntimeError):
    """Raised when an image provider cannot produce an image."""


def is_image_generation_config(config: ModelConfig) -> bool:
    return config.provider.lower() in {"doubao", "volcengine", "ark"} or "seedream" in config.model.lower()


def normalize_image_model(config: ModelConfig) -> str:
    model = (config.model or "").strip()
    return DOUBAO_IMAGE_MODEL_ALIASES.get(model, model)


def generate_doubao_image(
    config: ModelConfig,
    prompt: str,
    output_dir: Path,
    title: str,
    size: str = "2K",
    timeout_seconds: int = 120,
) -> GeneratedImage:
    """Generate one image through Volcano Ark's Seedream image endpoint."""
    if not config.api_key:
        raise ImageGenerationError("豆包/Seedream API Key 为空")

    output_dir.mkdir(parents=True, exist_ok=True)
    model = normalize_image_model(config)
    api_base = (config.api_base or DEFAULT_ARK_IMAGE_BASE).rstrip("/")
    endpoint = f"{api_base}/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "output_format": "png",
        "response_format": "url",
        "watermark": False,
    }
    raw = _post_json(endpoint, payload, config.api_key, timeout_seconds)
    image_data = (raw.get("data") or [{}])[0]
    filename = f"{_safe_filename(title)}.png"
    image_path = output_dir / filename

    b64_json = image_data.get("b64_json") or image_data.get("b64")
    source_url = image_data.get("url") or ""
    if b64_json:
        image_path.write_bytes(base64.b64decode(_strip_data_url_prefix(b64_json)))
    elif source_url:
        _download_file(source_url, image_path, timeout_seconds)
    else:
        raise ImageGenerationError(f"Seedream 响应中没有图片数据: {str(raw)[:300]}")

    return GeneratedImage(
        title=title,
        prompt=prompt,
        path=str(image_path),
        provider=config.provider,
        model=model,
        source_url=source_url,
        size=image_data.get("size") or size,
        metadata={"raw_keys": sorted(image_data.keys())},
    )


def _post_json(endpoint: str, payload: dict[str, Any], api_key: str, timeout_seconds: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ImageGenerationError(f"Seedream HTTP {exc.code}: {_redact(body)}") from exc
    except Exception as exc:
        raise ImageGenerationError(f"Seedream 请求失败: {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ImageGenerationError(f"Seedream 返回非 JSON: {body[:300]}") from exc


def _download_file(url: str, path: Path, timeout_seconds: int) -> None:
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            path.write_bytes(response.read())
    except Exception as exc:
        raise ImageGenerationError(f"图片 URL 下载失败: {exc}") from exc


def _strip_data_url_prefix(value: str) -> str:
    return value.split(",", 1)[1] if value.startswith("data:") and "," in value else value


def _safe_filename(text: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\s]+', "_", text).strip("._")
    return clean[:80] or "generated_image"


def _redact(text: str) -> str:
    return re.sub(r"(sk-[A-Za-z0-9_\-]{6})[A-Za-z0-9_\-]+", r"\1***", text)
