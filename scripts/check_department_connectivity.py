from __future__ import annotations

import asyncio
import base64
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_manager import ConfigManager
from src.comic_quality import review_comic_image
from src.image_generation import generate_doubao_image, is_image_generation_config
from src.llm.providers import LLMFactory, LLMMessage


AGENTS = ["zhongshu", "menxia", "shangshu", "libu", "hubu", "libu_comm", "bingbu", "xingbu", "gongbu"]
AGENT_NAMES = {
    "zhongshu": "中书省",
    "menxia": "门下省",
    "shangshu": "尚书省",
    "libu": "吏部",
    "hubu": "户部",
    "libu_comm": "礼部",
    "bingbu": "兵部",
    "xingbu": "刑部",
    "gongbu": "工部",
}


def _mask_status(value: str) -> str:
    return "SET" if value else "EMPTY"


async def _chat_probe(config) -> tuple[str, str]:
    if not config.api_key and config.provider != "ollama":
        return "missing_key", "api_key is empty"
    provider = LLMFactory.create(replace(config, max_tokens=16, temperature=0))
    response = await asyncio.wait_for(
        provider.chat([
            LLMMessage(role="system", content="Reply with exactly: pong"),
            LLMMessage(role="user", content="ping"),
        ]),
        timeout=45,
    )
    content = (response.content or "").strip()
    if content.startswith("[API错误]"):
        return "api_error", content[:260]
    return ("ok", content[:120]) if content else ("empty_response", "no text")


async def _vision_probe(config, sample_image: Path) -> tuple[str, str]:
    if not config.api_key:
        return "missing_key", "api_key is empty"
    if not sample_image.exists():
        return "missing_sample", str(sample_image)
    review = await asyncio.wait_for(
        review_comic_image(
            config,
            sample_image,
            {
                "kind": "connectivity_test",
                "source_id": "sample",
                "prompt": "请只判断图片是否可读取，不做创作评价。",
            },
        ),
        timeout=90,
    )
    return "ok", f"vision_status={review.status}; score={review.score}"


def _image_probe(config, output_dir: Path, cache: dict) -> tuple[str, str]:
    if not config.api_key:
        return "missing_key", "api_key is empty"
    cache_key = (config.provider, config.model, config.api_base, bool(config.api_key))
    if cache_key in cache:
        return cache[cache_key]
    image = generate_doubao_image(
        config,
        "AI漫剧模型连通性测试图，一张简单的电影感竖屏场景概念图，干净构图",
        output_dir,
        "seedream_department_connectivity",
    )
    path = Path(image.path)
    result = ("ok", f"generated={path.name}; bytes={path.stat().st_size}; model={image.model}")
    cache[cache_key] = result
    return result


async def main() -> None:
    cm = ConfigManager()
    offices = sys.argv[1:] or ["research", "comic"]
    sample = Path("output/workspaces/ws_5f0ad8c0/generated/01_character_char_01.png")
    output_dir = Path("output/model_tests/departments")
    image_cache: dict = {}
    rows = []
    for office in offices:
        for agent in AGENTS:
            cfg = cm.get_model_config(agent, office_id=office)
            status = "not_run"
            detail = ""
            kind = "chat"
            try:
                if is_image_generation_config(cfg):
                    kind = "image"
                    status, detail = _image_probe(cfg, output_dir, image_cache)
                elif "vl" in (cfg.model or "").lower() or "vision" in (cfg.model or "").lower():
                    kind = "vision"
                    status, detail = await _vision_probe(cfg, sample)
                else:
                    status, detail = await _chat_probe(cfg)
            except Exception as exc:
                status = "error"
                detail = f"{type(exc).__name__}: {exc}"[:260]
            rows.append({
                "office": office,
                "agent": agent,
                "agent_name": AGENT_NAMES.get(agent, agent),
                "provider": cfg.provider,
                "model": cfg.model,
                "key": _mask_status(cfg.api_key),
                "kind": kind,
                "status": status,
                "detail": detail,
            })
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
