"""Web 搜索和抓取工具 — 真实的网络数据获取能力"""

import json
import sys
import asyncio

import requests
from bs4 import BeautifulSoup


async def web_search(query: str, max_results: int = 5) -> dict:
    """搜索网页并返回结果列表 (支持 ddgs 和 duckduckgo_search)"""
    results = []

    # 尝试新版 ddgs 包
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:300],
                })
        if results:
            print(f"  [web_search] '{query[:50]}...' → {len(results)} 条", file=sys.stderr)
            return {"query": query, "results": results}
    except ImportError:
        pass
    except Exception as e:
        print(f"  [web_search] ddgs 失败: {e}", file=sys.stderr)

    # 回退到旧版 duckduckgo_search
    if not results:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")[:300],
                    })
            if results:
                print(f"  [web_search] (legacy) '{query[:50]}...' → {len(results)} 条", file=sys.stderr)
                return {"query": query, "results": results}
        except ImportError:
            pass
        except Exception as e:
            print(f"  [web_search] legacy 失败: {e}", file=sys.stderr)

    if not results:
        return {"query": query, "results": [], "note": "未找到结果, 尝试更换搜索词或使用英文关键词"}
    return {"query": query, "results": results}


async def web_fetch(url: str, extract_length: int = 3000) -> dict:
    """抓取网页内容并提取文本"""
    if not url.startswith(("http://", "https://")):
        return {"url": url, "error": "URL 必须以 http:// 或 https:// 开头"}

    try:
        # 在线程池中执行同步 HTTP 请求
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }, timeout=15, allow_redirects=True)
        )

        if resp.status_code != 200:
            return {"url": url, "error": f"HTTP {resp.status_code}", "content_preview": resp.text[:500]}

        soup = BeautifulSoup(resp.text, "html.parser")

        # 移除脚本和样式
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # 提取正文
        text = soup.get_text(separator="\n", strip=True)
        # 过滤空行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        cleaned = "\n".join(lines)

        title = soup.title.string if soup.title else url

        print(f"  [web_fetch] '{url[:60]}...' → {len(cleaned)} chars", file=sys.stderr)

        return {
            "url": url,
            "title": title.strip() if title else url,
            "content": cleaned[:extract_length],
            "content_length": len(cleaned),
            "truncated": len(cleaned) > extract_length,
        }

    except requests.Timeout:
        return {"url": url, "error": "请求超时"}
    except Exception as e:
        return {"url": url, "error": str(e)}


def register_web_tools(registry):
    """注册 Web 工具到注册表"""
    # web_search
    registry.register(
        name="web_search",
        description="搜索互联网获取最新信息、数据、新闻。返回标题、URL和摘要列表。适用于需要真实数据的场景。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词。用中英文混合搜索效果更好，如 '意大利面 行业报告 pasta industry market 2024'",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数，默认5",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=web_search,
    )

    # web_fetch
    registry.register(
        name="web_fetch",
        description="抓取指定 URL 的网页内容，提取正文文本。用于深入获取搜索结果中的具体数据。",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页 URL",
                },
                "extract_length": {
                    "type": "integer",
                    "description": "提取文本的最大长度（字符数），默认3000",
                    "default": 3000,
                },
            },
            "required": ["url"],
        },
        handler=web_fetch,
    )
