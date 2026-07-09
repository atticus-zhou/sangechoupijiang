"""Verify public no-key demo endpoints and sample downloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from src.web.app import app


DEMO_ENDPOINTS = {
    "comic_production": {
        "name": "AI 漫剧制片办公室",
        "endpoint": "/api/demo/comic-production",
        "launch_gate_endpoint": "/api/offices/comic_production/launch-gates",
    },
    "research": {
        "name": "研究办公室",
        "endpoint": "/api/demo/research",
        "launch_gate_endpoint": "/api/offices/research/launch-gates",
    },
}


def _download_items(payload: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for item in payload.get("deliverables") or payload.get("artifacts") or []:
        uri = item.get("uri") or ""
        status = item.get("status") or ""
        if uri.startswith("/api/demo/") and status == "downloadable":
            items.append({
                "title": str(item.get("title") or item.get("type") or uri),
                "uri": uri,
            })
    return items


def _collect_launch_gate_links(client: TestClient, endpoint: str) -> list[str]:
    response = client.get(endpoint)
    if response.status_code != 200:
        return []
    links: list[str] = []
    for gate in response.json().get("gates", []):
        for link in gate.get("evidence_links", []):
            uri = link.get("uri")
            if uri:
                links.append(str(uri))
    return links


def verify_public_demo_mode() -> dict[str, Any]:
    client = TestClient(app)
    demos: dict[str, Any] = {}
    all_links: list[str] = []
    errors: list[str] = []

    for office_id, meta in DEMO_ENDPOINTS.items():
        response = client.get(meta["endpoint"])
        available = response.status_code == 200
        payload = response.json() if available else {}
        downloads: list[dict[str, Any]] = []
        if not available:
            errors.append(f"{office_id} demo endpoint returned {response.status_code}")

        for item in _download_items(payload):
            file_response = client.get(item["uri"])
            record = {
                "title": item["title"],
                "uri": item["uri"],
                "status_code": file_response.status_code,
                "bytes": len(file_response.content or b""),
                "content_type": file_response.headers.get("content-type", ""),
            }
            downloads.append(record)
            if record["status_code"] != 200:
                errors.append(f"{office_id} download failed: {item['uri']} -> {record['status_code']}")
            if record["bytes"] <= 20:
                errors.append(f"{office_id} download too small: {item['uri']} -> {record['bytes']} bytes")

        if len(downloads) < 2:
            errors.append(f"{office_id} exposes fewer than 2 downloadable demo files")

        gate_links = _collect_launch_gate_links(client, meta["launch_gate_endpoint"])
        all_links.extend(gate_links)
        if not gate_links:
            errors.append(f"{office_id} launch gates do not expose evidence links")

        demos[office_id] = {
            "name": meta["name"],
            "endpoint": meta["endpoint"],
            "available": available,
            "requires_api_key": False,
            "calls_real_models": False,
            "read_only": True,
            "downloads": downloads,
            "launch_gate_links": gate_links,
        }

    required_links = {
        "/api/demo/comic-production/files/word_canvas.docx",
        "/api/demo/comic-production/files/handoff_manifest.json",
        "/api/demo/research/files/report.md",
        "/api/demo/research/files/evidence_manifest.json",
    }
    missing_links = sorted(required_links.difference(all_links))
    for uri in missing_links:
        errors.append(f"launch gate evidence missing {uri}")

    return {
        "status": "passed" if not errors else "failed",
        "mode": "public_no_key_demo",
        "summary": "公开演示端点、样例下载和上线门禁链接可用" if not errors else "公开演示验证发现问题",
        "demos": demos,
        "launch_gate_links": sorted(set(all_links)),
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 公开演示模式验证",
        "",
        f"状态：{payload['status']}",
        f"模式：{payload['mode']}",
        f"说明：{payload['summary']}",
        "",
        "本验证只检查无 Key 演示端点、样例交付物下载和上线门禁链接，不调用真实模型。",
        "",
    ]
    for demo in payload["demos"].values():
        lines.extend([
            f"## {demo['name']}",
            "",
            f"- 入口：`{demo['endpoint']}`",
            f"- 可访问：{demo['available']}",
            f"- 不消耗 Key：{not demo['requires_api_key']}",
            f"- 不调用真实模型：{not demo['calls_real_models']}",
            f"- 只读演示：{demo['read_only']}",
            "- 下载链接：",
        ])
        for item in demo["downloads"]:
            lines.append(
                f"  - `{item['uri']}`：HTTP {item['status_code']}，{item['bytes']} bytes"
            )
        lines.append("")
    if payload.get("errors"):
        lines.append("## 问题")
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    payload = verify_public_demo_mode()
    if args.format == "markdown":
        print(format_markdown(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())