"""Quality review helpers for the AI comic office."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.llm.providers import LLMFactory, ModelConfig


@dataclass
class ComicImageReview:
    status: str = "needs_review"
    score: int = 0
    issues: list[str] = field(default_factory=list)
    revision_prompt: str = ""
    raw: str = ""


def parse_comic_image_review(text: str) -> ComicImageReview:
    """Parse a vision model review. Falls back safely for non-JSON text."""
    raw = (text or "").strip()
    payload = _extract_json(raw)
    if not payload:
        return ComicImageReview(status="needs_review", raw=raw)
    status = str(payload.get("status") or payload.get("result") or "needs_review").lower()
    if status in {"pass", "passed", "ok", "合格", "通过"}:
        status = "pass"
    elif status in {"fail", "failed", "ng", "不合格", "失败"}:
        status = "fail"
    else:
        status = "needs_review"
    score = _as_int(payload.get("score"), default=0)
    issues = payload.get("issues") or payload.get("problems") or []
    if isinstance(issues, str):
        issues = [issues]
    revision_prompt = str(payload.get("revision_prompt") or payload.get("fix_prompt") or "").strip()
    return ComicImageReview(
        status=status,
        score=score,
        issues=[str(item).strip() for item in issues if str(item).strip()],
        revision_prompt=revision_prompt,
        raw=raw,
    )


def should_retry_image(review: ComicImageReview, minimum_score: int = 80) -> bool:
    return review.status == "fail" or (review.status == "needs_review" and 0 < review.score < minimum_score) or (
        review.status == "pass" and 0 < review.score < minimum_score
    )


def build_revised_prompt(original_prompt: str, review: ComicImageReview, attempt: int) -> str:
    issues = "；".join(review.issues) if review.issues else "上一版未达到一致性要求"
    fix = review.revision_prompt or "修正不一致之处，保持人物、服装、道具、场景和画风稳定"
    return "\n".join([
        original_prompt.strip(),
        "",
        f"第{attempt}次修正要求：{fix}",
        f"必须避免的问题：{issues}",
        "保持原始设定，禁止改变角色身份、画风方向、镜头用途和关键道具。",
    ]).strip()


async def review_comic_image(
    config: ModelConfig,
    image_path: str | Path,
    spec: dict,
) -> ComicImageReview:
    """Ask a vision-capable model to review a generated comic image."""
    if not config.api_key:
        return ComicImageReview(
            status="needs_review",
            raw="刑部模型没有配置 API Key，跳过自动视觉检查。",
        )
    path = Path(image_path)
    image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    llm = LLMFactory.create(config)
    response = await llm.chat_with_vision(
        text=_review_instruction(spec),
        images=[image_b64],
        system="你是AI漫剧办公室的刑部质检官，只检查生成图是否符合提示词和连续性要求。",
    )
    return parse_comic_image_review(response.content)


def _review_instruction(spec: dict) -> str:
    return "\n".join([
        "请检查这张AI漫剧资产图是否符合制作要求。",
        f"资产类型：{spec.get('kind', '')}",
        f"资产ID：{spec.get('source_id', '')}",
        f"原始提示词：{spec.get('prompt', '')}",
        "",
        "重点检查：人物脸型/服装是否稳定，关键道具是否存在，场景是否符合，画风是否一致，是否有明显畸形或不可用文字。",
        "只返回JSON，禁止 Markdown：",
        '{"status":"pass|fail|needs_review","score":0-100,"issues":["问题1"],"revision_prompt":"给生图模型的修正提示词"}',
    ])


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidates.insert(0, match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return value if isinstance(value, dict) else {}
    return {}


def _as_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default
