"""Drive the comic V2 browser UI through the review and delivery chain.

Prerequisites:
  1. Start the app with COMIC_V2_FIXTURE_MODE=1.
  2. Start Chrome with a CDP port, for example:
     chrome.exe --remote-debugging-port=9223 --user-data-dir=<temp-profile> http://127.0.0.1:8080/
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import time
import uuid
from pathlib import Path
import sys
from urllib.request import ProxyHandler, build_opener

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.web.app import config_manager


FIXTURE_PATH = Path("tests/fixtures/comic_v2_sample.json")


def seed_workspace() -> str:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    workspace_id = f"ws_browser_fixture_{str(uuid.uuid4())[:8]}"
    config_manager.create_workspace(
        workspace_id=workspace_id,
        office_id="comic_production",
        title=f"浏览器验证-{fixture['planner_payload']['title']}",
        brief="browser fixture verification",
    )
    confirmed = {
        "title": fixture["planner_payload"]["title"],
        "story_draft": fixture["source_story"],
        "script_hash": "browser-fixture",
        "script_version": 1,
    }
    config_manager.set_kv(
        f"comic_cabinet_session:{workspace_id}",
        json.dumps({"confirmed": True, "confirmed_script": confirmed}, ensure_ascii=False),
    )
    return workspace_id


class CdpClient:
    def __init__(self, ws):
        self.ws = ws
        self.counter = itertools.count(1)

    async def send(self, method: str, params: dict | None = None) -> dict:
        message_id = next(self.counter)
        await self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(await self.ws.recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    async def close(self) -> None:
        await self.ws.close()


def cdp_json(port: int, path: str) -> object:
    opener = build_opener(ProxyHandler({}))
    url = f"http://127.0.0.1:{port}{path}"
    last = ""
    for _ in range(10):
        with opener.open(url, timeout=5) as response:
            last = response.read().decode("utf-8")
        if last.strip():
            return json.loads(last)
        time.sleep(0.2)
    raise RuntimeError(f"CDP returned an empty response for {path}")


async def connect_cdp(ws_url: str) -> CdpClient:
    return CdpClient(await websockets.connect(ws_url, max_size=10_000_000, proxy=None))


async def verify_browser_flow(base_url: str, cdp_port: int, workspace_id: str) -> dict:
    version = cdp_json(cdp_port, "/json/version")
    browser = await connect_cdp(version["webSocketDebuggerUrl"])
    await browser.send("Target.createTarget", {"url": base_url})
    await asyncio.sleep(1)
    targets = cdp_json(cdp_port, "/json/list")
    pages = [item for item in targets if str(item.get("url", "")).startswith(base_url)]
    if not pages:
        raise RuntimeError(f"No Chrome target opened for {base_url}")
    page = await connect_cdp(pages[-1]["webSocketDebuggerUrl"])
    await page.send("Runtime.enable")
    await page.send("Page.enable")
    await asyncio.sleep(2)
    js = _browser_script(workspace_id)
    result = await page.send(
        "Runtime.evaluate",
        {"expression": js, "awaitPromise": True, "returnByValue": True},
    )
    await page.close()
    await browser.close()
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"])
    value = result.get("result", {}).get("value") or {}
    if not value.get("ok"):
        raise RuntimeError(value)
    return value


def _browser_script(workspace_id: str) -> str:
    return f"""
(async () => {{
  const workspaceId = {json.dumps(workspace_id)};
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const post = async (url, data = {{}}) => {{
    const response = await fetch(url, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(data)
    }});
    const payload = await response.json().catch(() => ({{}}));
    if (!response.ok || payload.detail) throw new Error(JSON.stringify(payload));
    return payload;
  }};
  const getStatus = async () => {{
    const response = await fetch(`/api/workspaces/${{workspaceId}}/comic/v2/status`);
    return response.json();
  }};
  const waitForStage = async (stage, timeout = 30000) => {{
    const start = Date.now();
    let status = null;
    while (Date.now() - start < timeout) {{
      status = await getStatus();
      if (status.stage === stage) return status;
      await sleep(250);
    }}
    throw new Error('timeout waiting for ' + stage + '; current=' + JSON.stringify(status));
  }};
  const clickButton = async (text, expectedStage, handler = '') => {{
    const start = Date.now();
    let el = null;
    while (Date.now() - start < 20000) {{
      const candidates = Array.from(document.querySelectorAll('button,a'))
        .filter(node => (node.innerText || '').includes(text));
      el = handler
        ? candidates.find(node => (node.getAttribute('onclick') || '').includes(handler))
        : candidates[0];
      if (el) break;
      await sleep(250);
    }}
    if (!el) {{
      throw new Error('button not found: ' + text + '; text=' + document.body.innerText.slice(0, 1200));
    }}
    el.click();
    const status = await waitForStage(expectedStage);
    await window.refreshComicV2Panel('browser advanced to ' + expectedStage);
    return status;
  }};
  window.prompt = message => {{
    if ((message || '').includes('视觉')) return '强化月灯裂纹、冷月光和古铜机械，不改变故事。';
    return '补齐中央月塔和裂纹月灯，移除故事里没有出现的资产。';
  }};
  window.navigate('comic_production');
  await sleep(1200);
  await window.selectComicWorkspace(workspaceId);
  await sleep(800);
  await post(`/api/workspaces/${{workspaceId}}/comic/v2/plan-confirmed`, {{}});
  await window.refreshComicV2Panel('browser fixture plan confirmed');
  let status = await waitForStage('visual_bible_review');
  const visited = [status.stage];
  status = await clickButton('退回视觉母版', 'visual_bible_review', 'reviseComicV2VisualBible');
  visited.push(status.stage);
  const visualVersion = status.style_version;
  status = await clickButton('确认视觉母版', 'asset_planning', 'approveComicV2VisualBible'); visited.push(status.stage);
  status = await clickButton('生成资产拆解审核包', 'asset_review', 'planComicV2Assets'); visited.push(status.stage);
  const firstAssetCount = status.asset_manifest.items.length;
  status = await clickButton('按意见重新拆解', 'asset_review', 'reviseComicV2Assets'); visited.push(status.stage);
  const revisedAssetCount = status.asset_manifest.items.length;
  const manifestVersion = status.asset_manifest.version;
  status = await clickButton('确认资产拆解', 'prompt_planning', 'approveComicV2Assets'); visited.push(status.stage);
  status = await clickButton('生成专属提示词', 'image_generation', 'planComicV2Prompts'); visited.push(status.stage);
  status = await clickButton('生成并质检基础资产图', 'document_generation', 'generateComicV2Images'); visited.push(status.stage);
  status = await clickButton('生成 Word 制片画布', 'ready_for_handoff', 'buildComicV2Delivery'); visited.push(status.stage);
  const text = document.body.innerText;
  return {{
    ok: true,
    workspaceId,
    visited,
    finalStage: status.stage,
    visualVersion,
    firstAssetCount,
    revisedAssetCount,
    manifestVersion,
    generatedImages: (status.image_production.records || []).length,
    audit: status.delivery.audit,
    download: status.delivery && status.delivery.uri,
    hasDownloadLink: text.includes('下载 Word 制片画布')
  }};
}})()
"""


async def amain() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/")
    parser.add_argument("--cdp-port", type=int, default=9223)
    parser.add_argument("--workspace-id", default="")
    args = parser.parse_args()
    workspace_id = args.workspace_id or seed_workspace()
    result = await verify_browser_flow(args.base_url, args.cdp_port, workspace_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(amain())
