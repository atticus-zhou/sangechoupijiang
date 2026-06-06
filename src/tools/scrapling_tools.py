"""Scrapling-style scraping tools with screenshot fallback.

These tools mirror the useful ideas from OpenClaw Scrapling: dynamic pages,
sessions, selector extraction, and screenshot fallback. Scrapling is optional;
when it is not installed we still keep the tool callable and fall back to the
local Chrome capture path where possible.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup
import requests

from src.browser_capture import capture_url


def scrapling_status() -> dict:
    try:
        import scrapling  # type: ignore
        return {"available": True, "package": "scrapling", "version": getattr(scrapling, "__version__", "")}
    except Exception as exc:
        return {
            "available": False,
            "package": "scrapling",
            "error": str(exc),
            "fallback": "browser_capture_url",
            "install_hint": "pip install 'scrapling[all]'",
        }


async def scrapling_scrape_url(
    url: str,
    selector: str = "body",
    extract: str = "text",
    dynamic: bool = True,
    stealth: bool = True,
    wait_for: str = "",
    output_path: str = "",
) -> dict:
    """Extract text/html/attributes from a URL, using Scrapling if available."""
    if not url.startswith(("http://", "https://")):
        return {"status": "failed", "error": "url must start with http:// or https://"}

    status = scrapling_status()
    if status["available"]:
        try:
            result = await asyncio.to_thread(
                _scrape_with_scrapling,
                url,
                selector,
                extract,
                dynamic,
                stealth,
                wait_for,
            )
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"status": "completed", "engine": "scrapling", **result}
        except Exception as exc:
            return {"status": "failed", "engine": "scrapling", "error": str(exc)}

    result = await asyncio.to_thread(_scrape_with_requests, url, selector, extract)
    result["engine"] = "requests_bs4_fallback"
    result["scrapling"] = status
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


async def scrapling_capture_url(
    url: str,
    title: str = "",
    wait_seconds: int = 6,
    output_dir: str = "output/scrapling_captures",
) -> dict:
    """Capture a dynamic page screenshot, using local Chrome as the stable fallback."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe_title = _safe_stem(title or "capture")
    output_path = out / f"{safe_title}.png"
    try:
        capture = await capture_url(url=url, output_path=output_path, wait_seconds=wait_seconds, full_page=True)
        return {
            "status": "captured",
            "engine": "chrome_cdp",
            "path": capture["path"],
            "size": capture["size"],
            "url": url,
            "scrapling": scrapling_status(),
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "scrapling": scrapling_status()}


async def scrapling_feigua_collect(keyword: str, wait_seconds: int = 6, output_dir: str = "") -> dict:
    """Scrapling-style Feigua workflow: scrape where possible, screenshot as evidence."""
    if not keyword.strip():
        return {"status": "failed", "error": "keyword is required"}
    base_dir = Path(output_dir or Path("output") / "scrapling_captures" / _safe_stem(keyword))
    base_dir.mkdir(parents=True, exist_ok=True)
    targets = [
        {"name": "飞瓜搜索", "url": f"https://www.feigua.cn/search?keyword={quote(keyword)}", "selector": "body"},
        {"name": "行业洞察入口", "url": "https://www.feigua.cn/data", "selector": "body"},
        {"name": "商品榜入口", "url": "https://www.feigua.cn/rank/goods", "selector": "body"},
        {"name": "品牌榜入口", "url": "https://www.feigua.cn/rank/brand", "selector": "body"},
        {"name": "达人榜入口", "url": "https://www.feigua.cn/rank/author", "selector": "body"},
    ]
    outputs = []
    for target in targets:
        scrape = await scrapling_scrape_url(
            url=target["url"],
            selector=target["selector"],
            extract="text",
            dynamic=True,
            stealth=True,
            output_path=str(base_dir / f"{_safe_stem(target['name'])}.json"),
        )
        shot = await scrapling_capture_url(
            url=target["url"],
            title=f"{keyword}_{target['name']}",
            wait_seconds=wait_seconds,
            output_dir=str(base_dir),
        )
        outputs.append({"target": target, "scrape": scrape, "screenshot": shot})
    return {
        "status": "completed" if any(o["screenshot"].get("status") == "captured" for o in outputs) else "needs_login",
        "keyword": keyword,
        "outputs": outputs,
        "note": "如果截图停留在登录页，请在本地浏览器完成飞瓜登录后重试。",
    }


def register_scrapling_tools(registry):
    registry.register(
        name="scrapling_status",
        description="检查 Scrapling 增强抓取能力是否可用；不可用时系统会退回浏览器截图。",
        parameters={"type": "object", "properties": {}},
        handler=lambda: _async_value(scrapling_status()),
    )
    registry.register(
        name="scrapling_scrape_url",
        description="Scrapling 风格网页抓取：支持动态页面、选择器抽取；未安装 Scrapling 时退回 requests+BeautifulSoup。",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标 URL"},
                "selector": {"type": "string", "description": "CSS selector", "default": "body"},
                "extract": {"type": "string", "description": "text/html", "default": "text"},
                "dynamic": {"type": "boolean", "description": "是否按动态页面处理", "default": True},
                "stealth": {"type": "boolean", "description": "是否使用 stealth fetcher", "default": True},
                "wait_for": {"type": "string", "description": "等待出现的 CSS selector", "default": ""},
                "output_path": {"type": "string", "description": "可选 JSON 输出路径", "default": ""},
            },
            "required": ["url"],
        },
        handler=scrapling_scrape_url,
    )
    registry.register(
        name="scrapling_capture_url",
        description="动态页面截图工具；用于 Scrapling 抓取失败、登录页调试或证据留存。",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标 URL"},
                "title": {"type": "string", "description": "截图名称", "default": ""},
                "wait_seconds": {"type": "integer", "description": "等待加载秒数", "default": 6},
                "output_dir": {"type": "string", "description": "截图输出目录", "default": "output/scrapling_captures"},
            },
            "required": ["url"],
        },
        handler=scrapling_capture_url,
    )
    registry.register(
        name="scrapling_feigua_collect",
        description="飞瓜调研增强取证：按 Skill 顺序尝试结构化抓取，并为每个关键页面保存截图。",
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "研究对象/品类关键词"},
                "wait_seconds": {"type": "integer", "description": "每页等待秒数", "default": 6},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
            },
            "required": ["keyword"],
        },
        handler=scrapling_feigua_collect,
    )


def _scrape_with_scrapling(url: str, selector: str, extract: str, dynamic: bool, stealth: bool, wait_for: str) -> dict:
    from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher  # type: ignore

    if dynamic:
        page = DynamicFetcher.fetch(url, network_idle=True)
    elif stealth:
        page = StealthyFetcher.fetch(url, headless=True)
    else:
        page = Fetcher.get(url)

    if wait_for and hasattr(page, "wait_for_selector"):
        page.wait_for_selector(wait_for)
    items = page.css(selector)
    if extract == "html":
        data = items.getall()
    else:
        data = items.css("::text").getall() if hasattr(items, "css") else items.getall()
    return {"url": url, "selector": selector, "extract": extract, "items": data[:100]}


def _scrape_with_requests(url: str, selector: str, extract: str) -> dict:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    selected = soup.select(selector)
    if extract == "html":
        items = [str(item) for item in selected]
    else:
        items = [item.get_text(" ", strip=True) for item in selected]
    return {"status": "completed", "url": url, "selector": selector, "items": items[:100], "http_status": resp.status_code}


async def _async_value(value: dict) -> dict:
    return value


def _safe_stem(text: str) -> str:
    import re
    return (re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", text).strip("_") or "capture")[:80]
