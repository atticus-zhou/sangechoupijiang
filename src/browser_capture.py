"""Local Chrome capture helper using the Chrome DevTools Protocol."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests
import websockets


DEFAULT_PORT = 9341


@dataclass
class BrowserSession:
    port: int
    profile_dir: Path
    chrome_path: Path


class BrowserCaptureError(RuntimeError):
    pass


def _local_request(method: str, url: str, **kwargs):
    session = requests.Session()
    session.trust_env = False
    return session.request(method, url, **kwargs)


def browser_executables(preferred: str = "edge") -> list[Path]:
    edge = [
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    chrome = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    if preferred == "edge":
        candidates = edge
    elif preferred == "chrome":
        candidates = chrome
    else:
        candidates = edge + chrome
    return [candidate for candidate in candidates if candidate.exists()]


def chrome_executable() -> Path | None:
    browsers = browser_executables("auto")
    return browsers[0] if browsers else None


def browser_profile_dir(base_dir: str | Path = ".") -> Path:
    path = (Path(base_dir).resolve() / "user_data" / "browser_profiles" / "research_edge_v3")
    path.mkdir(parents=True, exist_ok=True)
    return path


def browser_status(port: int = DEFAULT_PORT) -> dict:
    try:
        resp = _local_request("GET", f"http://127.0.0.1:{port}/json/version", timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "running": True,
                "port": port,
                "browser": data.get("Browser", ""),
                "websocket": bool(data.get("webSocketDebuggerUrl")),
            }
    except Exception:
        pass
    return {"running": False, "port": port}


def _browser_matches_preference(status: dict, preferred_browser: str) -> bool:
    browser = (status.get("browser") or "").lower()
    if preferred_browser == "edge":
        return "edg/" in browser
    if preferred_browser == "chrome":
        return "chrome/" in browser and "edg/" not in browser
    return True


def ensure_browser(
    start_url: str = "about:blank",
    visible: bool = True,
    port: int = DEFAULT_PORT,
    base_dir: str | Path = ".",
    preferred_browser: str = "edge",
) -> BrowserSession:
    browsers = browser_executables(preferred_browser)
    if not browsers:
        raise BrowserCaptureError(f"没有找到可用的 {preferred_browser} 浏览器，请先安装或切换浏览器配置。")

    profile = browser_profile_dir(base_dir)
    status = browser_status(port)
    if status["running"]:
        if _browser_matches_preference(status, preferred_browser):
            return BrowserSession(port=port, profile_dir=profile, chrome_path=browsers[0])
        raise BrowserCaptureError(
            f"浏览器调试端口 {port} 已被 {status.get('browser', '其他浏览器')} 占用。"
            "请关闭旧的取证浏览器，或重启后再试。"
        )

    last_error = ""
    for chrome in browsers:
        args = [
            str(chrome),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            "--new-window",
            start_url or "about:blank",
        ]
        if not visible:
            args.insert(1, "--headless=new")
            args.insert(2, "--disable-gpu")
        _launch_browser(args)
        try:
            _wait_for_browser(port)
            return BrowserSession(port=port, profile_dir=profile, chrome_path=chrome)
        except BrowserCaptureError as exc:
            last_error = str(exc)
            continue
    raise BrowserCaptureError(last_error or "浏览器调试端口没有启动成功。")


def _launch_browser(args: list[str]) -> None:
    if os.name == "nt":
        exe = str(args[0]).replace("'", "''")
        ps_script = (
            "$argsList = @("
            + ",".join("'" + arg.replace("'", "''") + "'" for arg in args[1:])
            + "); "
            + f"Start-Process -FilePath '{exe}' -ArgumentList $argsList -WindowStyle Normal"
        )
        subprocess.Popen(
            [
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_for_browser(port: int) -> None:
    deadline = time.time() + 12
    while time.time() < deadline:
        if browser_status(port)["running"]:
            return
        time.sleep(0.25)
    raise BrowserCaptureError("浏览器调试端口没有启动成功。")


async def capture_url(
    url: str,
    output_path: str | Path,
    wait_seconds: float = 5,
    full_page: bool = True,
    viewport_width: int = 1440,
    viewport_height: int = 1000,
    port: int = DEFAULT_PORT,
    base_dir: str | Path = ".",
) -> dict:
    if not url.startswith(("http://", "https://")):
        raise BrowserCaptureError("截图 URL 必须以 http:// 或 https:// 开头。")

    ensure_browser(start_url="about:blank", visible=True, port=port, base_dir=base_dir)
    tab = _new_tab(port, url)
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        raise BrowserCaptureError("无法连接浏览器调试会话。")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024, proxy=None) as ws:
        cdp = _CDP(ws)
        await cdp.send("Page.enable")
        await cdp.send("Runtime.enable")
        await cdp.send("Page.navigate", {"url": url})
        await asyncio.sleep(max(1, min(wait_seconds, 30)))
        await cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": viewport_width,
            "height": viewport_height,
            "deviceScaleFactor": 1,
            "mobile": False,
        })
        if full_page:
            metrics = await cdp.send("Runtime.evaluate", {
                "expression": (
                    "({width: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth, 1440), "
                    "height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 1000)})"
                ),
                "returnByValue": True,
            })
            value = metrics.get("result", {}).get("result", {}).get("value", {}) or {}
            width = int(min(max(value.get("width", viewport_width), viewport_width), 6000))
            height = int(min(max(value.get("height", viewport_height), viewport_height), 12000))
            await cdp.send("Emulation.setDeviceMetricsOverride", {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": False,
            })
        shot = await cdp.send("Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": bool(full_page),
        })
    image = base64.b64decode(shot.get("result", {}).get("data", ""))
    if not image:
        raise BrowserCaptureError("浏览器没有返回截图数据。")
    output.write_bytes(image)
    return {
        "path": str(output),
        "size": len(image),
        "url": url,
        "full_page": full_page,
    }


def feigua_capture_targets(keyword: str) -> list[dict]:
    return [
        {
            "name": "飞瓜抖音数据入口",
            "url": "https://dy3.feigua.cn/",
            "note": f"用于进入飞瓜抖音电商与直播数据平台，后续登录后围绕“{keyword}”检索。",
        },
        {
            "name": "飞瓜商品功能入口",
            "url": "https://dy3.feigua.cn/home/Product",
            "note": "用于确认商品榜、商品分析、爆品分析等功能入口。",
        },
        {
            "name": "飞瓜商品搜索榜说明",
            "url": "https://dy3.feigua.cn/article/detail/809.html",
            "note": "用于确认商品搜索榜、爆款热卖榜、搜索热度榜、搜索趋势榜的功能路径。",
        },
        {
            "name": "飞瓜达人行业榜样例",
            "url": "https://dy3.feigua.cn/rank/tag/41/month/202604.html",
            "note": "用于截取公开达人行业榜样例，登录后应替换为与研究对象相关的商品/品牌/达人榜。",
        },
    ]


async def capture_feigua_plan(
    keyword: str,
    output_dir: str | Path,
    wait_seconds: float = 6,
    limit: int = 4,
) -> list[dict]:
    targets = feigua_capture_targets(keyword)[: max(1, min(limit, 4))]
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    captures = []
    for target in targets:
        stem = _safe_stem(f"{keyword}_{target['name']}")
        path = output / f"{uuid.uuid4().hex[:8]}_{stem}.png"
        try:
            result = await capture_url(
                url=target["url"],
                output_path=path,
                wait_seconds=wait_seconds,
                full_page=True,
            )
            captures.append({
                **target,
                "status": "captured",
                "path": result["path"],
                "size": result["size"],
            })
        except Exception as exc:
            captures.append({
                **target,
                "status": "failed",
                "error": str(exc),
            })
    return captures


async def open_login_page(
    url: str = "https://dy3.feigua.cn/",
    port: int = DEFAULT_PORT,
    base_dir: str | Path = ".",
) -> dict:
    """Open Feigua and click the visible login entry when present."""
    session = ensure_browser(start_url=url, visible=True, port=port, base_dir=base_dir)
    tab = _last_page_tab(port)
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        raise BrowserCaptureError("无法连接浏览器登录页。")
    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024, proxy=None) as ws:
        cdp = _CDP(ws)
        await cdp.send("Runtime.enable")
        await cdp.send("Page.enable")
        click_result = await cdp.send("Runtime.evaluate", {
            "expression": """
(() => {
  const isVisible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const dispatchClick = (el) => {
    el.scrollIntoView({block: 'center', inline: 'center'});
    ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(type => {
      el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
    });
  };
  const candidates = Array.from(document.querySelectorAll('a,button'));
  const login =
    document.querySelector('.js-douyin-login') ||
    document.querySelector('.btns-login') ||
    candidates.find(el => isVisible(el) && /注册\\s*\\/\\s*登录|登录|登陆/.test((el.innerText || el.textContent || '').trim()));
  if (login) {
    dispatchClick(login);
    return {clicked: true, text: (login.innerText || login.textContent || '').trim(), href: login.href || ''};
  }
  const trial = candidates.find(el => isVisible(el) && /免费试用|立即试用/.test((el.innerText || el.textContent || '').trim()));
  if (trial) {
    dispatchClick(trial);
    return {clicked: true, text: (trial.innerText || trial.textContent || '').trim(), href: trial.href || ''};
  }
  return {clicked: false, reason: '没有找到可见的登录入口'};
})()
""",
            "returnByValue": True,
        })
        await asyncio.sleep(2.5)
        state = await cdp.send("Runtime.evaluate", {
            "expression": """
({
  title: document.title,
  url: location.href,
  text: document.body.innerText.slice(0, 3000),
  hasLoginDialog: /微信登录|手机登录|扫码登录|登录\\/注册飞瓜/.test(document.body.innerText || ''),
  loginDialogText: (() => {
    const text = document.body.innerText || '';
    const idx = Math.max(text.indexOf('微信登录'), text.indexOf('手机登录'), text.indexOf('扫码登录'));
    return idx >= 0 ? text.slice(Math.max(0, idx - 80), idx + 260) : '';
  })()
})
""",
            "returnByValue": True,
        })
    return {
        "status": "opened",
        "url": url,
        "port": session.port,
        "profile_dir": str(session.profile_dir),
        "browser": str(session.chrome_path),
        "click": click_result.get("result", {}).get("result", {}).get("value", {}),
        "page": state.get("result", {}).get("result", {}).get("value", {}),
    }


async def feigua_login_state(port: int = DEFAULT_PORT) -> dict:
    """Return whether the current Feigua browser profile appears logged in."""
    tab = _last_page_tab(port)
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        raise BrowserCaptureError("无法连接浏览器页面。")
    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024, proxy=None) as ws:
        cdp = _CDP(ws)
        await cdp.send("Runtime.enable")
        state = await cdp.send("Runtime.evaluate", {
            "expression": """
(() => {
  const text = document.body.innerText || '';
  const hasLoginDialog = /微信登录|手机登录|扫码登录|登录\\/注册飞瓜/.test(text);
  const hasLoginEntry = /注册\\s*\\/\\s*登录/.test(text);
  const loggedSignals = [
    /退出登录|账号中心|个人中心|我的套餐|工作台|进入系统|数据概览|我的收藏/.test(text),
    !!document.querySelector('[href*="Logout"], [href*="logout"], .user-info, .avatar, .user-name'),
    location.pathname.toLowerCase().includes('/app') || location.pathname.toLowerCase().includes('/dashboard')
  ];
  return {
    title: document.title,
    url: location.href,
    hasLoginDialog,
    hasLoginEntry,
    loggedIn: loggedSignals.some(Boolean) && !hasLoginDialog,
    textSample: text.slice(0, 1000)
  };
})()
""",
            "returnByValue": True,
        })
    return state.get("result", {}).get("result", {}).get("value", {}) or {}


async def wait_for_feigua_login(
    timeout_seconds: int = 300,
    poll_seconds: float = 3,
    port: int = DEFAULT_PORT,
) -> dict:
    """Wait until the user finishes Feigua login in the visible browser."""
    deadline = time.time() + max(10, timeout_seconds)
    last_state: dict = {}
    while time.time() < deadline:
        try:
            last_state = await feigua_login_state(port=port)
            if last_state.get("loggedIn"):
                return {"status": "logged_in", "state": last_state}
        except Exception as exc:
            last_state = {"error": str(exc)}
        await asyncio.sleep(max(1, poll_seconds))
    return {"status": "timeout", "state": last_state}


def _safe_stem(text: str) -> str:
    import re
    return (re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", text).strip("_") or "capture")[:80]


def _last_page_tab(port: int) -> dict:
    tabs = _local_request("GET", f"http://127.0.0.1:{port}/json/list", timeout=5).json()
    pages = [tab for tab in tabs if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl")]
    if not pages:
        raise BrowserCaptureError("没有找到可控制的浏览器页面。")
    return pages[-1]


def _new_tab(port: int, url: str) -> dict:
    endpoint = f"http://127.0.0.1:{port}/json/new?{quote(url, safe='')}"
    try:
        resp = _local_request("PUT", endpoint, timeout=5)
    except Exception:
        resp = _local_request("GET", endpoint, timeout=5)
    if resp.status_code >= 400:
        raise BrowserCaptureError(f"创建浏览器标签页失败: HTTP {resp.status_code}")
    return resp.json()


class _CDP:
    def __init__(self, ws):
        self.ws = ws
        self.next_id = 0

    async def send(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        msg_id = self.next_id
        await self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise BrowserCaptureError(f"CDP {method} 失败: {data['error']}")
                return data
