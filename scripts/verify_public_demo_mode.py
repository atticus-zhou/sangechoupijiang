"""Verify public no-key demo endpoints, showcase manifest, and downloads."""

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


def _verify_showcase_manifest(client: TestClient, errors: list[str]) -> dict[str, Any]:
    response = client.get("/api/demo/public-showcase")
    if response.status_code != 200:
        errors.append(f"public showcase manifest returned {response.status_code}")
        return {
            "status_code": response.status_code,
            "mode": "",
            "audience_path_count": 0,
            "featured_demo_count": 0,
        }

    payload = response.json()
    audience_paths = payload.get("audience_paths") or []
    featured_demos = payload.get("featured_demos") or []
    portfolio_embed = payload.get("portfolio_embed") or {}
    public_deployment = payload.get("public_deployment") or {}
    static_export = public_deployment.get("static_export") or {}
    interview_script = portfolio_embed.get("interview_demo_script") or []
    handoff_inventory = portfolio_embed.get("handoff_inventory") or {}
    real_production_claim = portfolio_embed.get("real_production_claim") or {}
    if payload.get("mode") != "public_no_key_showcase":
        errors.append("public showcase manifest has unexpected mode")
    if payload.get("requires_api_key") is not False:
        errors.append("public showcase manifest must not require API key")
    if payload.get("calls_real_models") is not False:
        errors.append("public showcase manifest must not call real models")
    if len(audience_paths) < 3:
        errors.append("public showcase manifest needs at least 3 audience paths")
    if len(featured_demos) < 2:
        errors.append("public showcase manifest needs at least 2 featured demos")
    if not portfolio_embed.get("repository_url"):
        errors.append("public showcase manifest must expose a repository URL for portfolio pages")
    if len(portfolio_embed.get("sample_deliverables") or []) < 5:
        errors.append("portfolio embed must expose at least 5 sample deliverables, including the real production claim report")
    for item in portfolio_embed.get("sample_deliverables") or []:
        if not item.get("reader_guidance"):
            errors.append(f"sample deliverable missing reader guidance: {item.get('title') or item.get('uri')}")
        if len(item.get("acceptance_signals") or []) < 3:
            errors.append(f"sample deliverable missing acceptance signals: {item.get('title') or item.get('uri')}")
    reading_guide = portfolio_embed.get("deliverable_reading_guide") or []
    if len(reading_guide) < 4:
        errors.append("portfolio embed must expose a 4-step deliverable reading guide")
    for item in reading_guide:
        if not str(item.get("uri") or "").startswith("/api/demo/"):
            errors.append(f"reading guide item has invalid demo uri: {item.get('title') or item.get('uri')}")
        if not item.get("look_for") or not item.get("proves"):
            errors.append(f"reading guide item missing look_for/proves: {item.get('title') or item.get('uri')}")
    if not any((item.get("kind") == "screenshot_target") for item in portfolio_embed.get("workflow_showcase") or []):
        errors.append("portfolio embed must include screenshot targets for the main workflow")
    if handoff_inventory.get("uri") != "/api/demo/comic-production/handoff-inventory":
        errors.append("portfolio embed must expose the comic handoff inventory endpoint")
    if handoff_inventory.get("production_verified_count") not in (0, None):
        errors.append("public showcase must not claim real comic production verification from demo inventory")
    if not handoff_inventory.get("safe_public_claim"):
        errors.append("portfolio embed handoff inventory must include a safe public claim")
    if real_production_claim.get("uri") != "/api/demo/comic-production/claim-report":
        errors.append("portfolio embed must expose the comic real production claim report endpoint")
    if real_production_claim.get("claim_level") != "demo_structure_only":
        errors.append("public showcase fixed sample must remain demo_structure_only")
    if real_production_claim.get("can_claim_real_quality") is not False:
        errors.append("public showcase must not claim real production quality from the fixed sample")
    if not real_production_claim.get("forbidden_public_claims"):
        errors.append("real production claim report must include forbidden public claims")
    if len(interview_script) < 4:
        errors.append("portfolio embed must expose a 4-step interview demo script")
    for item in interview_script:
        if not item.get("visitor_action") or not item.get("product_response") or not item.get("proof") or not item.get("boundary"):
            errors.append(f"interview demo script item is incomplete: {item.get('title') or item.get('order')}")
    if public_deployment.get("mode") != "demo_only":
        errors.append("public deployment profile must be demo_only")
    if public_deployment.get("allows_real_model_calls") is not False:
        errors.append("public deployment profile must forbid real model calls")
    if public_deployment.get("allows_workspace_writes") is not False:
        errors.append("public deployment profile must forbid workspace writes")
    if static_export.get("command") != "python scripts/export_public_showcase.py":
        errors.append("public deployment profile must expose the static export command")
    if static_export.get("entrypoint") != "dist/public-showcase/index.html":
        errors.append("public deployment profile must expose the static showcase entrypoint")
    if static_export.get("requires_backend") is not False or static_export.get("requires_api_key") is not False:
        errors.append("static showcase export must be backend-free and no-key")

    return {
        "status_code": response.status_code,
        "mode": payload.get("mode", ""),
        "product_name": payload.get("product_name", ""),
        "audience_path_count": len(audience_paths),
        "featured_demo_count": len(featured_demos),
        "safe_for_public_portfolio": bool(payload.get("safe_for_public_portfolio")),
        "portfolio_deliverable_count": len(portfolio_embed.get("sample_deliverables") or []),
        "deliverables_with_reader_guidance": sum(
            1
            for item in portfolio_embed.get("sample_deliverables") or []
            if item.get("reader_guidance") and len(item.get("acceptance_signals") or []) >= 3
        ),
        "reading_guide_count": len(reading_guide),
        "reading_guide_ready_count": sum(
            1
            for item in reading_guide
            if str(item.get("uri") or "").startswith("/api/demo/") and item.get("look_for") and item.get("proves")
        ),
        "interview_script_count": len(interview_script),
        "interview_script_ready_count": sum(
            1
            for item in interview_script
            if item.get("visitor_action") and item.get("product_response") and item.get("proof") and item.get("boundary")
        ),
        "handoff_inventory_uri": handoff_inventory.get("uri", ""),
        "handoff_inventory_manifest_count": handoff_inventory.get("manifest_count", 0),
        "handoff_inventory_production_verified_count": handoff_inventory.get("production_verified_count", 0),
        "handoff_inventory_safe_public_claim": handoff_inventory.get("safe_public_claim", ""),
        "real_production_claim_uri": real_production_claim.get("uri", ""),
        "real_production_claim_level": real_production_claim.get("claim_level", ""),
        "real_production_can_claim_real_quality": real_production_claim.get("can_claim_real_quality"),
        "public_deployment_mode": public_deployment.get("mode", ""),
        "static_export_command": static_export.get("command", ""),
        "static_export_entrypoint": static_export.get("entrypoint", ""),
        "static_export_backend_free": static_export.get("requires_backend") is False,
    }


def verify_public_demo_mode() -> dict[str, Any]:
    client = TestClient(app)
    demos: dict[str, Any] = {}
    all_links: list[str] = []
    errors: list[str] = []
    showcase_manifest = _verify_showcase_manifest(client, errors)
    inventory_response = client.get("/api/demo/comic-production/handoff-inventory")
    inventory_payload = inventory_response.json() if inventory_response.status_code == 200 else {}
    if inventory_response.status_code != 200:
        errors.append(f"comic handoff inventory endpoint returned {inventory_response.status_code}")
    if inventory_payload.get("calls_real_models") is not False:
        errors.append("comic handoff inventory must not call real models")
    if inventory_payload.get("requires_api_key") is not False:
        errors.append("comic handoff inventory must not require API key")
    if inventory_payload.get("production_verified_count", 0) != 0:
        errors.append("fixed public inventory must not claim real production quality verification")
    claim_response = client.get("/api/demo/comic-production/claim-report")
    claim_payload = claim_response.json() if claim_response.status_code == 200 else {}
    if claim_response.status_code != 200:
        errors.append(f"comic claim report endpoint returned {claim_response.status_code}")
    if claim_payload.get("calls_real_models") is not False:
        errors.append("comic claim report must not call real models")
    if claim_payload.get("requires_api_key") is not False:
        errors.append("comic claim report must not require API key")
    if claim_payload.get("claim_level") != "demo_structure_only":
        errors.append("fixed public claim report must remain demo_structure_only")
    if claim_payload.get("can_claim_real_quality") is not False:
        errors.append("fixed public claim report must not claim real production quality")

    for office_id, meta in DEMO_ENDPOINTS.items():
        response = client.get(meta["endpoint"])
        available = response.status_code == 200
        payload = response.json() if available else {}
        downloads: list[dict[str, Any]] = []
        quality_benchmark: dict[str, Any] = {}
        honest_quality_gate: dict[str, Any] = {}
        if not available:
            errors.append(f"{office_id} demo endpoint returned {response.status_code}")

        if office_id == "comic_production" and available:
            quality_benchmark = payload.get("quality_benchmark") or {}
            honest_quality_gate = next(
                (
                    item
                    for item in payload.get("quality_gates") or []
                    if item.get("id") == "honest_quality_claim"
                ),
                {},
            )
            if quality_benchmark.get("status") != "demo_structure_verified":
                errors.append("comic production demo must claim demo_structure_verified")
            if quality_benchmark.get("package_quality_score") != 100:
                errors.append("comic production fixed demo must score 100/100 on the structural benchmark")
            if quality_benchmark.get("package_quality_ready") is not True:
                errors.append("comic production fixed demo must pass the structural package gate")
            if quality_benchmark.get("production_quality_verified") is not False:
                errors.append("comic production fixed demo must not claim real production image quality")
            if quality_benchmark.get("recommended_recovery"):
                errors.append("comic production passing demo must not expose a recovery action")
            if honest_quality_gate.get("status") != "passed":
                errors.append("comic production demo honest quality gate must pass")

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
            "quality_benchmark": quality_benchmark,
            "honest_quality_gate": honest_quality_gate,
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
        "summary": "公开展示清单、演示端点、样例下载、真实生产声明和上线门禁链接可用" if not errors else "公开演示验证发现问题",
        "showcase_manifest": showcase_manifest,
        "comic_handoff_inventory": {
            "status_code": inventory_response.status_code,
            "status": inventory_payload.get("status", ""),
            "manifest_count": inventory_payload.get("manifest_count", 0),
            "production_verified_count": inventory_payload.get("production_verified_count", 0),
            "demo_only_count": inventory_payload.get("demo_only_count", 0),
            "needs_review_count": inventory_payload.get("needs_review_count", 0),
            "safe_public_claim": inventory_payload.get("safe_public_claim", ""),
        },
        "comic_real_production_claim": {
            "status_code": claim_response.status_code,
            "claim_level": claim_payload.get("claim_level", ""),
            "quality_claim": claim_payload.get("quality_claim", ""),
            "can_claim_real_quality": claim_payload.get("can_claim_real_quality"),
            "downstream_status": claim_payload.get("downstream_status", ""),
        },
        "demos": demos,
        "launch_gate_links": sorted(set(all_links)),
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    manifest = payload.get("showcase_manifest") or {}
    inventory = payload.get("comic_handoff_inventory") or {}
    claim = payload.get("comic_real_production_claim") or {}
    lines = [
        "# 公开演示模式验证",
        "",
        f"状态：{payload['status']}",
        f"模式：{payload['mode']}",
        f"说明：{payload['summary']}",
        "",
        "本验证只检查无 Key 演示端点、公开展示清单、样例交付物下载和上线门禁链接，不调用真实模型。",
        "",
        "## 公开展示清单",
        "",
        f"- 入口：`/api/demo/public-showcase`",
        f"- HTTP：{manifest.get('status_code')}",
        f"- 模式：{manifest.get('mode')}",
        f"- 访客路径：{manifest.get('audience_path_count')} 条",
        f"- 推荐演示：{manifest.get('featured_demo_count')} 个",
        f"- 可公开作品集展示：{manifest.get('safe_for_public_portfolio')}",
        f"- 作品集样例交付物：{manifest.get('portfolio_deliverable_count')} 个",
        f"- 带阅读说明的样例交付物：{manifest.get('deliverables_with_reader_guidance')} 个",
        f"- 交付物阅读顺序：{manifest.get('reading_guide_count')} 步，其中 {manifest.get('reading_guide_ready_count')} 步可复核",
        f"- 面试演示脚本：{manifest.get('interview_script_count')} 步，其中 {manifest.get('interview_script_ready_count')} 步可复用",
        f"- 漫剧交付盘点：{inventory.get('manifest_count')} 份，真实质量通过 {inventory.get('production_verified_count')} 份，结构样例 {inventory.get('demo_only_count')} 份",
        f"- 漫剧公开质量声明：{inventory.get('safe_public_claim')}",
        f"- 公开部署模式：{manifest.get('public_deployment_mode')}",
        "",
    ]
    lines.insert(
        -1,
        f"- AI comic claim report: {claim.get('claim_level')} / real_quality={claim.get('can_claim_real_quality')} / downstream={claim.get('downstream_status')}",
    )
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
        benchmark = demo.get("quality_benchmark") or {}
        if benchmark:
            lines.extend([
                f"- 固定样例质量基准：{benchmark.get('package_quality_score', 0)}/100",
                f"- 质量声明：`{benchmark.get('status', '')}`",
                f"- 已验证真实模型画质：{benchmark.get('production_quality_verified')}",
            ])
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
