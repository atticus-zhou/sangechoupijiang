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

from src.web.app import app


DEFAULT_OUTPUT = REPO_ROOT / "dist" / "public-showcase"
TEMPLATE_ROOT = REPO_ROOT / "src" / "web" / "static_showcase"
PRODUCT_SCREENSHOT = REPO_ROOT / "docs" / "assets" / "public-showcase-desktop.png"


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
    return Path("downloads", *relative.parts)


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
    for demo in showcase.get("featured_demos") or []:
        for item in demo.get("downloads") or []:
            uri = str(item.get("uri") or "")
            if uri:
                uris.add(uri)
    portfolio = showcase.get("portfolio_embed") or {}
    for group in ("sample_deliverables", "deliverable_reading_guide"):
        for item in portfolio.get(group) or []:
            uri = str(item.get("uri") or "")
            if uri:
                uris.add(uri)
    return sorted(uris)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        source_mode = static_showcase.get("mode")
        static_showcase["mode"] = "public_no_key_static_showcase"
        static_showcase["static_export"] = {
            "source_mode": source_mode,
            "entrypoint": "index.html",
            "requires_backend": False,
            "contains_api_keys": False,
            "download_count": len(download_records),
            "visual_asset": "assets/public-showcase-desktop.png",
            "generated_by": "python scripts/export_public_showcase.py",
        }
        static_showcase["safety_boundaries"] = [
            "静态展示只包含固定样例、实际产品截图和四份公开样例交付物。",
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
                "四份交付物已经随静态站点一起导出，每个链接都附带阅读重点和验收信号。"
            )
        deployment = static_showcase.setdefault("public_deployment", {})
        deployment["mode"] = "static_demo_only"
        deployment["allowed_route_prefixes"] = []
        deployment["requires_backend"] = False
        deployment["contains_api_keys"] = False

        _write_json(staging / "showcase.json", static_showcase)
        for office_id, payload in demo_payloads.items():
            _write_json(staging / "data" / f"{office_id}.json", payload)
        _write_json(staging / claim_report_path, _rewrite_uris(claim_report, uri_map))
        data_json = json.dumps(static_showcase, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        (staging / "data.js").write_text(
            f"window.__PUBLIC_SHOWCASE__ = {data_json};\n",
            encoding="utf-8",
        )

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

    return {
        "status": "passed",
        "mode": "public_no_key_static_export",
        "output_dir": str(target),
        "entrypoint": str(target / "index.html"),
        "download_count": len(download_records),
        "file_count": len(file_records) + 1,
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
