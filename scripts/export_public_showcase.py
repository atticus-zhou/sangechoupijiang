"""Export the no-key public showcase as a self-contained static site."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from scripts.verify_public_docs_readability import _find_suspicious_markers
from src.web.app import app


DEFAULT_OUTPUT = REPO_ROOT / "dist" / "public-showcase"
TEMPLATE_ROOT = REPO_ROOT / "src" / "web" / "static_showcase"
PRODUCT_SCREENSHOT = REPO_ROOT / "docs" / "assets" / "public-showcase-desktop.png"
EXTRA_REVIEWABLE_DOCS = [
    {
        "source_path": REPO_ROOT / "docs" / "OFFICE_EXPANSION_DECISION_BRIEF.md",
        "local_uri": "downloads/platform/office-expansion-decision-brief.md",
        "title": "办公室扩展决策简报",
        "office_id": "platform",
        "office_name": "平台扩展治理",
        "type": "decision_brief",
        "reader_guidance": "先看当前主力办公室、研究办公室边界和未来办公室排序，确认产品不是靠堆 UI 入口扩展。",
        "look_for": "研究办公室 staged demo 边界、ecommerce_selection 优先级、schema gate、recovery actions 和 public claim report 准入门槛。",
        "proves": "证明新办公室扩展顺序和暂缓原因已经写成可读文档，并接入发布门禁。",
        "acceptance_signals": [
            "明确 AI 漫剧制片办公室仍是主力办公室",
            "明确研究办公室不能宣称全自动飞瓜会员级采集",
            "明确未来办公室必须先补办公室专属 schema gate 和 recovery actions",
        ],
    },
    {
        "source_path": REPO_ROOT / "docs" / "COMIC_REAL_RUN_EVIDENCE_INTAKE.md",
        "local_uri": "downloads/comic-production/comic-real-run-evidence-intake.md",
        "title": "AI 漫剧真实运行证据收口单",
        "office_id": "comic_production",
        "office_name": "AI 漫剧制片办公室",
        "type": "real_run_evidence_intake",
        "reader_guidance": "先看真实模型跑完后需要收哪些证据，再判断样例包能不能升级成真实生产质量。",
        "look_for": "model_evidence、image_production_evidence、image_quality_summary、asset_identity_cards、reference_asset_chain、prompt_strategy_lineage 和 downstream_handoff_decision。",
        "proves": "证明 demo 到真实生产质量之间有可审核的证据收口标准，而不是凭页面观感或口头判断。",
        "acceptance_signals": [
            "明确无 Key 样例不能宣称真实画质",
            "明确人物和道具资产应是干净白底或极简背景",
            "明确真实质量声明必须通过 production_quality_verified=true",
        ],
    }
]


def _safe_output_path(output_dir: Path | str) -> Path:
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    if resolved == REPO_ROOT or REPO_ROOT not in resolved.parents:
        raise ValueError("Static showcase output must stay inside the repository.")
    if any(part.lower() in {".git", "src", "tests", "user_data", "output"} for part in resolved.relative_to(REPO_ROOT).parts):
        raise ValueError("Static showcase output must use a dedicated build directory such as dist/public-showcase.")
    return resolved


def _download_path(uri: str) -> Path:
    prefix = "/api/demo/"
    if not uri.startswith(prefix):
        raise ValueError(f"Public download is outside the no-key demo boundary: {uri}")
    relative = PurePosixPath(uri[len(prefix):])
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Public download has an unsafe path: {uri}")
    parts = list(relative.parts)
    leaf = parts[-1]
    if "." not in leaf:
        parts[-1] = f"{leaf}.json"
    return Path("downloads", *parts)


def _rewrite_uris(value: Any, uri_map: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_uris(item, uri_map) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_uris(item, uri_map) for item in value]
    if isinstance(value, str):
        return uri_map.get(value, value)
    return value


def _showcase_download_uris(showcase: dict[str, Any]) -> list[str]:
    uris: set[str] = set()
    claim_report_uri = "/api/demo/comic-production/claim-report"
    for demo in showcase.get("featured_demos") or []:
        for item in demo.get("downloads") or []:
            uri = str(item.get("uri") or "")
            if uri:
                uris.add(uri)
    portfolio = showcase.get("portfolio_embed") or {}
    for group in ("sample_deliverables", "deliverable_reading_guide"):
        for item in portfolio.get(group) or []:
            uri = str(item.get("uri") or "")
            if uri and uri != claim_report_uri:
                uris.add(uri)
    return sorted(uris)


def _download_catalog_metadata(static_showcase: dict[str, Any]) -> dict[str, dict[str, Any]]:
    portfolio = static_showcase.get("portfolio_embed") or {}
    metadata: dict[str, dict[str, Any]] = {}
    for group in ("deliverable_reading_guide", "sample_deliverables"):
        for item in portfolio.get(group) or []:
            local_uri = str(item.get("uri") or "")
            if not local_uri or local_uri.startswith("/"):
                continue
            entry = metadata.setdefault(local_uri, {})
            for key in (
                "order",
                "title",
                "office_id",
                "office_name",
                "type",
                "reader_guidance",
                "look_for",
                "proves",
                "acceptance_signals",
                "claim_level",
                "can_claim_real_quality",
            ):
                value = item.get(key)
                if value not in (None, "", []):
                    entry[key] = value
    for doc in EXTRA_REVIEWABLE_DOCS:
        entry = metadata.setdefault(str(doc["local_uri"]), {})
        entry.update({key: value for key, value in doc.items() if key != "source_path"})
        entry.setdefault("order", 90)
    return metadata


def _build_download_catalog(static_showcase: dict[str, Any], file_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metadata = _download_catalog_metadata(static_showcase)
    catalog: list[dict[str, Any]] = []
    for record in file_records:
        local_uri = str(record.get("local_uri") or "")
        meta = metadata.get(local_uri, {})
        catalog.append(
            {
                "order": meta.get("order", 99),
                "title": meta.get("title") or Path(local_uri).name,
                "local_uri": local_uri,
                "source_uri": record.get("source_uri", ""),
                "bytes": record.get("bytes", 0),
                "sha256": record.get("sha256", ""),
                "content_type": record.get("content_type", ""),
                "office_id": meta.get("office_id", ""),
                "office_name": meta.get("office_name", ""),
                "type": meta.get("type", ""),
                "reader_guidance": meta.get("reader_guidance", ""),
                "look_for": meta.get("look_for", ""),
                "proves": meta.get("proves", ""),
                "acceptance_signals": meta.get("acceptance_signals", []),
                "claim_level": meta.get("claim_level", ""),
                "can_claim_real_quality": meta.get("can_claim_real_quality", ""),
            }
        )
    return sorted(catalog, key=lambda item: (int(item.get("order") or 99), str(item.get("local_uri") or "")))


def _append_extra_reviewable_docs_to_reading_guide(static_showcase: dict[str, Any]) -> None:
    portfolio = static_showcase.setdefault("portfolio_embed", {})
    reading_guide = portfolio.setdefault("deliverable_reading_guide", [])
    existing_uris = {str(item.get("uri") or "") for item in reading_guide}
    for doc in EXTRA_REVIEWABLE_DOCS:
        local_uri = str(doc["local_uri"])
        if local_uri in existing_uris:
            continue
        reading_guide.append(
            {
                "order": doc.get("order", 90),
                "title": doc["title"],
                "uri": local_uri,
                "office_id": doc["office_id"],
                "office_name": doc["office_name"],
                "type": doc["type"],
                "reader_guidance": doc["reader_guidance"],
                "look_for": doc["look_for"],
                "proves": doc["proves"],
                "acceptance_signals": doc["acceptance_signals"],
            }
        )


def _build_visitor_acceptance_guide(static_showcase: dict[str, Any]) -> dict[str, Any]:
    portfolio = static_showcase.get("portfolio_embed") or {}
    deployment = static_showcase.get("public_deployment") or {}
    live_verification = deployment.get("live_verification") or {}
    ci_verification = deployment.get("ci_verification") or (portfolio.get("portfolio_integration") or {}).get("portfolio_ci_proof") or {}
    release_badge = portfolio.get("release_badge") or {}
    claim = portfolio.get("real_production_claim") or {}
    research_claim = portfolio.get("research_claim_boundary") or {}
    fast_review = portfolio.get("fast_review_route") or []
    download_catalog = static_showcase.get("download_catalog") or []
    fallback = deployment.get("reviewer_fallback_packet") or portfolio.get("reviewer_fallback_packet") or {}

    return {
        "mode": "public_no_key_visitor_acceptance",
        "title": "三个臭皮匠公开演示验收路线",
        "safe_for_public_portfolio": static_showcase.get("safe_for_public_portfolio") is True,
        "requires_backend": False,
        "requires_api_key": False,
        "calls_real_models": False,
        "recommended_minutes": 5,
        "release_badge": {
            "status": release_badge.get("status", ""),
            "mode": release_badge.get("mode", ""),
            "primary_gate": release_badge.get("primary_gate", ""),
            "can_claim_real_quality": release_badge.get("can_claim_real_quality", False),
        },
        "visitor_route": [
            *[
                {
                    "order": int(item.get("order") or index + 1),
                    "title": item.get("title", ""),
                    "viewer_action": item.get("viewer_action", ""),
                    "proof": item.get("proof", ""),
                    "next_anchor": item.get("next_anchor", ""),
                }
                for index, item in enumerate(fast_review)
            ],
            {
                "order": len(fast_review) + 1,
                "title": "逐个检查可下载交付物",
                    "viewer_action": "按 download_acceptance 里的九个文件逐个打开，确认每个文件都有阅读重点、证明点和 sha256。",
                "proof": "访客可以离开网页直接复核 Word 画布、handoff manifest、声明报告和研究材料，不需要相信页面文案。",
                "next_anchor": "#catalog-title",
            },
            {
                "order": len(fast_review) + 2,
                "title": "线上没刷新时打开离线评审包",
                "viewer_action": "如果线上 /three-stooges/ 还是旧页面或 404，运行 pack:reviewer 生成离线包，把 OPEN_THIS_FIRST.txt 作为评审入口。",
                "proof": "离线评审包不含 API Key，也不需要后端，可以证明静态展示、样例下载物和构建信息已经准备好。",
                "next_anchor": "#integration-title",
            },
            {
                "order": len(fast_review) + 3,
                "title": "最后确认线上状态不能跳过",
                "viewer_action": "部署到个人网站后运行 npm run check:online，只有通过后才把 /three-stooges/ 发给面试官。",
                "proof": "本地静态包准备好不等于线上 Vercel 已更新，公开链接必须由线上检查证明。",
                "next_anchor": "#repro-title",
            },
        ],
        "download_acceptance": [
            {
                "order": item.get("order", 99),
                "title": item.get("title", ""),
                "local_uri": item.get("local_uri", ""),
                "bytes": item.get("bytes", 0),
                "sha256": item.get("sha256", ""),
                "proves": item.get("proves") or item.get("reader_guidance") or item.get("look_for") or "",
                "acceptance_signals": item.get("acceptance_signals") or [],
            }
            for item in download_catalog
        ],
        "claim_boundaries": {
            "comic": {
                "claim_level": claim.get("claim_level", ""),
                "can_claim_real_quality": claim.get("can_claim_real_quality", False),
                "allowed_public_claims": claim.get("allowed_public_claims", []),
                "forbidden_public_claims": claim.get("forbidden_public_claims", []),
            },
            "research": {
                "claim_level": research_claim.get("claim_level", ""),
                "can_claim_full_automation": research_claim.get("can_claim_full_automation", False),
                "forbidden_public_claims": research_claim.get("forbidden_public_claims", []),
            },
        },
        "live_verification": {
            "status": live_verification.get("status", "external_required"),
            "live_url": live_verification.get("live_url", "https://www.atticus.asia/three-stooges/"),
            "doctor_command": live_verification.get("doctor_command", "npm run doctor:deploy"),
            "check_command": live_verification.get("check_command", "npm run check:online"),
            "do_not_claim_live_until": "npm run check:online passes",
        },
        "reviewer_fallback_packet": {
            "status": fallback.get("status", "available_when_live_route_stale"),
            "packet_dir": fallback.get("packet_dir", "tmp/three-cobblers-reviewer-packet"),
            "archive_path": fallback.get("archive_path", "tmp/three-cobblers-reviewer-packet.zip"),
            "open_first": fallback.get("open_first", "tmp/three-cobblers-reviewer-packet/OPEN_THIS_FIRST.txt"),
            "commands": fallback.get("commands", []),
            "proves": fallback.get("proves", []),
            "does_not_prove": fallback.get("does_not_prove", []),
            "forbidden_materials": fallback.get("forbidden_materials", []),
        },
        "ci_verification": {
            "status": ci_verification.get("status", "repo_static_checks"),
            "workflow_path": ci_verification.get("workflow_path", ".github/workflows/three-cobblers-showcase.yml"),
            "commands": ci_verification.get("commands", []),
            "live_authority": ci_verification.get("live_authority", "npm run check:online"),
            "do_not_claim_live_until": ci_verification.get("do_not_claim_live_until", "npm run check:online passes"),
        },
        "must_not_include": [
            "API Key",
            "config.yaml",
            ".env",
            "Cookie",
            "user_data/",
            "output/",
            "runtime_logs/",
        ],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _text_integrity_findings(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    text_suffixes = {".html", ".js", ".json", ".md", ".txt"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        relative = path.relative_to(root).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            findings.append({"file": relative, "issue": "utf8_decode_error", "markers": [str(exc)]})
            continue
        markers = _find_suspicious_markers(content)
        if markers:
            findings.append({"file": relative, "issue": "suspicious_text_markers", "markers": markers})
    return findings


def export_public_showcase(output_dir: Path | str = DEFAULT_OUTPUT) -> dict[str, Any]:
    target = _safe_output_path(output_dir)
    if not TEMPLATE_ROOT.is_dir():
        raise FileNotFoundError(f"Static showcase template is missing: {TEMPLATE_ROOT}")
    if not PRODUCT_SCREENSHOT.is_file():
        raise FileNotFoundError(f"Public showcase screenshot is missing: {PRODUCT_SCREENSHOT}")

    client = TestClient(app)
    response = client.get("/api/demo/public-showcase")
    if response.status_code != 200:
        raise RuntimeError(f"Public showcase endpoint returned {response.status_code}.")
    showcase = response.json()
    if showcase.get("requires_api_key") is not False or showcase.get("calls_real_models") is not False:
        raise RuntimeError("Static export refused a showcase that can read API keys or call real models.")
    if showcase.get("safe_for_public_portfolio") is not True:
        raise RuntimeError("Static export refused a showcase that is not marked safe for a public portfolio.")

    staging = target.parent / f".{target.name}.building"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(TEMPLATE_ROOT, staging)

    try:
        assets_dir = staging / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PRODUCT_SCREENSHOT, assets_dir / "public-showcase-desktop.png")

        uri_map: dict[str, str] = {}
        download_records: list[dict[str, Any]] = []
        for uri in _showcase_download_uris(showcase):
            local_path = _download_path(uri)
            file_response = client.get(uri)
            if file_response.status_code != 200 or len(file_response.content or b"") <= 20:
                raise RuntimeError(f"Public showcase download failed: {uri}")
            destination = staging / local_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(file_response.content)
            local_uri = local_path.as_posix()
            uri_map[uri] = local_uri
            download_records.append(
                {
                    "source_uri": uri,
                    "local_uri": local_uri,
                    "bytes": destination.stat().st_size,
                    "content_type": file_response.headers.get("content-type", ""),
                    "sha256": _sha256(destination),
                }
            )

        demo_payloads: dict[str, dict[str, Any]] = {}
        for demo in showcase.get("featured_demos") or []:
            office_id = str(demo.get("office_id") or "")
            demo_uri = str(demo.get("demo_uri") or "")
            if not office_id or not demo_uri.startswith("/api/demo/"):
                raise RuntimeError("Public showcase contains an invalid featured demo.")
            demo_response = client.get(demo_uri)
            if demo_response.status_code != 200:
                raise RuntimeError(f"Featured demo returned {demo_response.status_code}: {demo_uri}")
            uri_map[demo_uri] = f"#office-{office_id}"
            demo_payloads[office_id] = _rewrite_uris(demo_response.json(), uri_map)

        claim_report_uri = "/api/demo/comic-production/claim-report"
        claim_response = client.get(claim_report_uri)
        if claim_response.status_code != 200:
            raise RuntimeError(f"Comic production claim report returned {claim_response.status_code}.")
        claim_report = _rewrite_uris(claim_response.json(), uri_map)
        claim_report_path = "data/comic_production_claim_report.json"
        uri_map[claim_report_uri] = claim_report_path

        static_showcase = _rewrite_uris(showcase, uri_map)
        _write_json(staging / claim_report_path, _rewrite_uris(claim_report, uri_map))
        claim_path = staging / claim_report_path
        reviewable_records = download_records + [
            {
                "source_uri": claim_report_uri,
                "local_uri": claim_report_path,
                "bytes": claim_path.stat().st_size,
                "content_type": "application/json",
                "sha256": _sha256(claim_path),
            }
        ]
        for doc in EXTRA_REVIEWABLE_DOCS:
            source_path = Path(doc["source_path"])
            if not source_path.is_file():
                raise FileNotFoundError(f"Reviewable public doc is missing: {source_path}")
            local_uri = str(doc["local_uri"])
            destination = staging / local_uri
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            reviewable_records.append(
                {
                    "source_uri": source_path.relative_to(REPO_ROOT).as_posix(),
                    "local_uri": local_uri,
                    "bytes": destination.stat().st_size,
                    "content_type": "text/markdown; charset=utf-8",
                    "sha256": _sha256(destination),
                }
            )
        source_mode = static_showcase.get("mode")
        static_showcase["mode"] = "public_no_key_static_showcase"
        _append_extra_reviewable_docs_to_reading_guide(static_showcase)
        static_showcase["download_catalog"] = _build_download_catalog(static_showcase, reviewable_records)
        static_showcase["static_export"] = {
            "source_mode": source_mode,
            "entrypoint": "index.html",
            "requires_backend": False,
            "contains_api_keys": False,
            "download_count": len(download_records),
            "reviewable_file_count": len(static_showcase["download_catalog"]),
            "download_catalog_includes_claim_report": True,
            "visual_asset": "assets/public-showcase-desktop.png",
            "generated_by": "python scripts/export_public_showcase.py",
        }
        static_showcase["safety_boundaries"] = [
            "静态展示只包含固定样例、实际产品截图、八份公开样例下载物、真实生产声明报告、真实运行证据收口单和办公室扩展决策简报，共十一个可复核文件。",
            "页面运行时不连接 FastAPI，不读取 config.yaml、环境变量、Cookie、登录态或本地用户工作区。",
            "不要把个人 API Key、真实用户数据或运行产物复制进静态目录。",
            "真实生产继续走本地模式，由使用者填写自己的模型 Key。",
        ]
        interview_script = (static_showcase.get("portfolio_embed") or {}).get("interview_demo_script") or []
        if len(interview_script) >= 1:
            interview_script[0]["product_response"] = (
                "静态包在导出时读取 /api/demo/public-showcase；访客打开页面时只读取随包的 data.js 和固定下载物。"
            )
        if len(interview_script) >= 3:
            interview_script[2]["product_response"] = (
                "八份公开下载物已经随静态站点一起导出，连同声明报告、真实运行证据收口单和办公室扩展决策简报构成十一个可复核文件，每个链接都附带阅读重点和验收信号。"
            )
        deployment = static_showcase.setdefault("public_deployment", {})
        deployment["mode"] = "static_demo_only"
        deployment["allowed_route_prefixes"] = []
        deployment["requires_backend"] = False
        deployment["contains_api_keys"] = False
        deployment["live_verification"] = {
            "status": "external_required",
            "live_url": "https://www.atticus.asia/three-stooges/",
            "authority": "personal_website_check_online",
            "doctor_command": "npm run doctor:deploy",
            "check_command": "npm run check:online",
            "ship_command": "npm run ship:vercel",
            "failure_meaning": "The static package is ready, but the production Vercel domain may still be serving an older deployment.",
        }
        deployment.setdefault(
            "reviewer_fallback_packet",
            (static_showcase.get("portfolio_embed") or {}).get("reviewer_fallback_packet") or {},
        )
        visitor_acceptance_guide = _build_visitor_acceptance_guide(static_showcase)
        visitor_acceptance_path = "data/visitor_acceptance_guide.json"
        static_showcase["visitor_acceptance_guide"] = {
            "uri": visitor_acceptance_path,
            "status": visitor_acceptance_guide["mode"],
            "step_count": len(visitor_acceptance_guide["visitor_route"]),
            "download_count": len(visitor_acceptance_guide["download_acceptance"]),
            "live_verification_status": visitor_acceptance_guide["live_verification"]["status"],
        }

        _write_json(staging / "showcase.json", static_showcase)
        _write_json(staging / visitor_acceptance_path, visitor_acceptance_guide)
        for office_id, payload in demo_payloads.items():
            _write_json(staging / "data" / f"{office_id}.json", payload)
        data_json = json.dumps(static_showcase, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        (staging / "data.js").write_text(
            f"window.__PUBLIC_SHOWCASE__ = {data_json};\n",
            encoding="utf-8",
        )
        portfolio_integration = (static_showcase.get("portfolio_embed") or {}).get("portfolio_integration") or {}
        ci_verification = (static_showcase.get("public_deployment") or {}).get("ci_verification") or portfolio_integration.get("portfolio_ci_proof") or {}
        deploy_manifest = {
            "mode": "public_no_key_portfolio_deploy",
            "recommended_path": "static_export",
            "entrypoint": "index.html",
            "source_dir": "dist/public-showcase",
            "standalone_deploy_directory": ".",
            "personal_site_target": "public/three-stooges/",
            "personal_site_url_path": "/three-stooges/",
            "live_url": "https://www.atticus.asia/three-stooges/",
            "requires_backend": False,
            "requires_api_key": False,
            "calls_real_models": False,
            "allows_workspace_writes": False,
            "live_verification": {
                "status": "external_required",
                "authority": "personal_website_check_online",
                "doctor_command": "npm run doctor:deploy",
                "check_command": "npm run check:online",
                "ship_command": "npm run ship:vercel",
                "requires_vercel_authorization": True,
                "passes_when": "https://www.atticus.asia/three-stooges/ and sample downloads return HTTP 200 from the personal website repository check.",
                "do_not_claim_live_until": "npm run check:online passes",
            },
            "ci_verification": {
                "status": ci_verification.get("status", "repo_static_checks"),
                "repository": ci_verification.get("repository", "https://github.com/atticus-zhou/me"),
                "workflow_path": ci_verification.get("workflow_path", ".github/workflows/three-cobblers-showcase.yml"),
                "proves": ci_verification.get("proves", []),
                "does_not_prove": ci_verification.get("does_not_prove", []),
                "commands": ci_verification.get("commands", []),
                "live_authority": ci_verification.get("live_authority", "npm run check:online"),
                "do_not_claim_live_until": ci_verification.get("do_not_claim_live_until", "npm run check:online passes"),
            },
            "reviewer_fallback_packet": (static_showcase.get("public_deployment") or {}).get("reviewer_fallback_packet") or {},
            "required_files": [
                "index.html",
                "data.js",
                "app.js",
                "style.css",
                "showcase.json",
                "export-manifest.json",
                "assets/public-showcase-desktop.png",
                "data/comic_production.json",
                "data/research.json",
                "data/comic_production_claim_report.json",
                "data/visitor_acceptance_guide.json",
                "downloads/",
            ],
            "sample_download_count": len(download_records),
            "verification_commands": [
                "python scripts/verify_public_demo_mode.py --format markdown",
                "python scripts/export_public_showcase.py",
                "python scripts/verify_static_public_showcase.py --format markdown",
                "python scripts/verify_release_readiness.py --format markdown",
                "cd E:/trae/me/personal-website-v2 && npm run check:reviewer-packet",
                "cd E:/trae/me/personal-website-v2 && npm run pack:reviewer",
                "cd E:/trae/me/personal-website-v2 && npm run check:reviewer-packet:generated",
                "cd E:/trae/me/personal-website-v2 && npm run doctor:deploy",
                "cd E:/trae/me/personal-website-v2 && npm run check:online",
            ],
            "forbidden_public_assets": [
                "config.yaml",
                ".env",
                "API Key",
                "Cookie",
                "user_data/",
                "output/",
                "runtime_logs/",
                "browser profile",
            ],
            "integration_options": portfolio_integration.get("integration_options") or [],
            "operator_checklist": [
                "确认只发布 dist/public-showcase 里的静态文件。",
                "确认八份样例下载物都能从页面下载。",
                "确认公开页面没有真实生产入口、API Key、Cookie、用户数据或运行产物。",
                "确认页面仍显示 demo-only、safe_public_demo 和 demo_structure_only。",
                "在个人网站仓库运行 npm run doctor:deploy，先区分本地包、Vercel 授权和线上旧部署。",
                "如果线上还没刷新，运行 npm run pack:reviewer 生成离线评审包，再运行 npm run check:reviewer-packet:generated 验证。",
                "确认个人网站线上 /three-stooges/ 只有在 npm run check:online 通过后才对外宣称 live。",
            ],
        }
        _write_json(staging / "portfolio-deploy-manifest.json", deploy_manifest)

        file_records = []
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            file_records.append(
                {
                    "path": path.relative_to(staging).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
        export_manifest = {
            "mode": "public_no_key_static_export",
            "entrypoint": "index.html",
            "requires_backend": False,
            "requires_api_key": False,
            "calls_real_models": False,
            "download_count": len(download_records),
            "downloads": download_records,
            "files": file_records,
        }
        _write_json(staging / "export-manifest.json", export_manifest)

        if target.exists():
            shutil.rmtree(target)
        staging.replace(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    text_files = [
        path
        for path in target.rglob("*")
        if path.is_file() and path.suffix.lower() in {".html", ".js", ".json", ".md", ".txt"}
    ]
    text_integrity_findings = _text_integrity_findings(target)

    return {
        "status": "passed",
        "mode": "public_no_key_static_export",
        "output_dir": str(target),
        "entrypoint": str(target / "index.html"),
        "download_count": len(download_records),
        "file_count": len(file_records) + 1,
        "text_integrity_status": "passed" if not text_integrity_findings else "failed",
        "text_integrity_scanned_files": len(text_files),
        "text_integrity_findings": text_integrity_findings,
        "requires_backend": False,
        "requires_api_key": False,
        "calls_real_models": False,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Export a static, no-key public showcase.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory inside the repository.")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()
    payload = export_public_showcase(args.output)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Static showcase exported: {payload['entrypoint']}")
        print(f"Files: {payload['file_count']}; downloads: {payload['download_count']}")
        print("Backend required: False; API Key required: False; real model calls: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
