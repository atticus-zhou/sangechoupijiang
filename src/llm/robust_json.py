"""Small helpers for resilient LLM JSON parsing and retry.

LLM responses often contain Markdown fences, explanation text, or tiny JSON
mistakes. These helpers keep that mess at the boundary instead of leaking it
into product workflows.
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar


T = TypeVar("T")


def parse_json_object(text: str) -> dict:
    """Parse a JSON object from noisy LLM text.

    The repair scope is deliberately conservative: extract one balanced object,
    remove Markdown fences, trim trailing commas, normalize smart quotes, and
    fall back to Python literal parsing for simple single-quoted objects.
    """
    candidate = _extract_object(text or "")
    if not candidate:
        return {}
    repaired = _repair_json(candidate)
    for value in (candidate, repaired):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            continue
        return parsed if isinstance(parsed, dict) else {}
    try:
        parsed = ast.literal_eval(repaired)
    except (SyntaxError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    delay_seconds: float = 0.25,
) -> T:
    """Retry a transient async operation a small number of times."""
    last_error: Exception | None = None
    for index in range(max(1, attempts)):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if index < attempts - 1 and delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
    assert last_error is not None
    raise last_error


def _extract_object(text: str) -> str:
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "")
    start = cleaned.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escape = False
    quote = ""
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
            continue
        if char in {'"', "'"}:
            in_string = True
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : index + 1].strip()
    return cleaned[start:].strip()


def _repair_json(candidate: str) -> str:
    value = candidate.strip()
    value = (
        value.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    value = re.sub(r",\s*([}\]])", r"\1", value)
    return value
