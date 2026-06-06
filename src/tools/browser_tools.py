"""Browser automation tools for evidence screenshots."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from src.browser_capture import (
    BrowserCaptureError,
    capture_feigua_plan,
    capture_url,
    ensure_browser,
    open_login_page,
)


async def browser_start_login(url: str = "https://dy3.feigua.cn/") -> dict:
    """Open a visible local browser so the user can log in once."""
    try:
        result = await open_login_page(url)
        return {
            **result,
            "status": "opened",
            "url": url,
            "note": "请在弹出的浏览器中登录；登录态会保存在本地资料目录。",
        }
    except BrowserCaptureError as exc:
        return {"status": "failed", "error": str(exc)}


async def browser_capture_url(url: str, title: str = "", wait_seconds: int = 6) -> dict:
    """Capture one URL into output/browser_captures."""
    out_dir = Path("output") / "browser_captures"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = title or "capture"
    path = out_dir / f"{uuid.uuid4().hex[:8]}_{_safe_stem(stem)}.png"
    try:
        result = await capture_url(url=url, output_path=path, wait_seconds=wait_seconds, full_page=True)
        return {"status": "captured", **result}
    except BrowserCaptureError as exc:
        return {"status": "failed", "url": url, "error": str(exc)}


async def browser_capture_feigua_plan(keyword: str, wait_seconds: int = 6, limit: int = 4) -> dict:
    """Capture standard Feigua evidence pages for a research keyword."""
    if not keyword.strip():
        return {"status": "failed", "error": "keyword is required"}
    out_dir = Path("output") / "browser_captures" / _safe_stem(keyword)
    captures = await capture_feigua_plan(
        keyword=keyword,
        output_dir=out_dir,
        wait_seconds=wait_seconds,
        limit=limit,
    )
    return {
        "status": "completed" if any(c.get("status") == "captured" for c in captures) else "failed",
        "keyword": keyword,
        "captures": captures,
    }


def register_browser_tools(registry):
    registry.register(
        name="browser_start_login",
        description="打开本地 Chrome/Edge 登录窗口，用于飞瓜、抖音、电商后台等需要账号的平台。账号密码只在本地浏览器里输入。",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要打开的登录页面 URL", "default": "https://dy3.feigua.cn/"},
            },
        },
        handler=browser_start_login,
    )
    registry.register(
        name="browser_capture_url",
        description="使用本地浏览器打开指定 URL 并保存整页截图，适合调试或已知页面取证。",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要截图的页面 URL"},
                "title": {"type": "string", "description": "截图名称", "default": ""},
                "wait_seconds": {"type": "integer", "description": "等待页面加载秒数", "default": 6},
            },
            "required": ["url"],
        },
        handler=browser_capture_url,
    )
    registry.register(
        name="browser_capture_feigua_plan",
        description="按飞瓜市场调研 Skill 的标准路径，为研究关键词自动打开飞瓜相关页面并截图。",
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "研究对象/类目关键词，例如 民用无人机、鼠标、七色糙米"},
                "wait_seconds": {"type": "integer", "description": "每个页面等待加载秒数", "default": 6},
                "limit": {"type": "integer", "description": "最多截图页面数，1-4", "default": 4},
            },
            "required": ["keyword"],
        },
        handler=browser_capture_feigua_plan,
    )


def _safe_stem(text: str) -> str:
    import re
    return (re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", text).strip("_") or "capture")[:80]
