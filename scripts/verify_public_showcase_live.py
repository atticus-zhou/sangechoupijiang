"""Verify a deployed no-key public showcase URL.

This script checks the deployed static site itself. It does not read local
config, API keys, cookies, or workspace data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import ProxyHandler, Request, build_opener


REQUIRED_STATIC_FILES = (
    "index.html",
    "showcase.json",
    "export-manifest.json",
    "data/visitor_acceptance_guide.json",
    "data/comic_production_claim_report.json",
    "downloads/comic-production/files/word_canvas.docx",
    "downloads/comic-production/files/handoff_manifest.json",
)


def _normalize_base_url(value: str) -> str:
    url = str(value or "").strip()
    if not url:
        raise ValueError("URL is required.")
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://.")
    return url if url.endswith("/") else f"{url}/"


def _fetch(url: str, *, timeout: float) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "three-cobblers-live-verifier/1.0"})
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read()
            headers = dict(response.headers.items())
            return {
                "url": url,
                "status_code": int(response.status),
                "bytes": len(body),
                "content_type": headers.get("Content-Type", ""),
                "sha256": hashlib.sha256(body).hexdigest(),
                "body": body,
            }
    except HTTPError as exc:
        return {
            "url": url,
            "status_code": int(exc.code),
            "bytes": 0,
            "content_type": "",
            "sha256": "",
            "body": b"",
            "error": str(exc),
        }
    except URLError as exc:
        return {
            "url": url,
            "status_code": 0,
            "bytes": 0,
            "content_type": "",
            "sha256": "",
            "body": b"",
            "error": str(exc.reason),
        }
    except TimeoutError as exc:
        return {
            "url": url,
            "status_code": 0,
            "bytes": 0,
            "content_type": "",
            "sha256": "",
            "body": b"",
            "error": f"timeout: {exc}",
        }


def _body_records(records: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {path: {key: value for key, value in record.items() if key != "body"} for path, record in records.items()}


def _json_from(record: dict[str, Any], errors: list[str], label: str) -> dict[str, Any]:
    try:
        return json.loads(record.get("body", b"").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is not valid UTF-8 JSON: {exc}")
        return {}


def verify_public_showcase_live(url: str, *, timeout: float = 15.0) -> dict[str, Any]:
    base_url = _normalize_base_url(url)
    errors: list[str] = []
    records: dict[str, dict[str, Any]] = {}

    for path in REQUIRED_STATIC_FILES:
        target = base_url if path == "index.html" else urljoin(base_url, path)
        record = _fetch(target, timeout=timeout)
        records[path] = record
        if record["status_code"] != 200:
            errors.append(f"{path} returned HTTP {record['status_code']}")
        elif record["bytes"] <= 20:
            errors.append(f"{path} is too small to be a valid public artifact")

    fetched = _body_records(records)
    showcase = _json_from(records["showcase.json"], errors, "showcase.json") if fetched["showcase.json"]["status_code"] == 200 else {}
    manifest = _json_from(records["export-manifest.json"], errors, "export-manifest.json") if fetched["export-manifest.json"]["status_code"] == 200 else {}
    visitor = _json_from(records["data/visitor_acceptance_guide.json"], errors, "visitor_acceptance_guide.json") if fetched["data/visitor_acceptance_guide.json"]["status_code"] == 200 else {}
    claim = _json_from(records["data/comic_production_claim_report.json"], errors, "comic_production_claim_report.json") if fetched["data/comic_production_claim_report.json"]["status_code"] == 200 else {}

    if showcase:
        if showcase.get("mode") != "public_no_key_static_showcase":
            errors.append("showcase.json has an unexpected mode")
        for flag in ("requires_api_key", "calls_real_models"):
            if showcase.get(flag) is not False:
                errors.append(f"showcase.json must keep {flag}=False")
        if showcase.get("safe_for_public_portfolio") is not True:
            errors.append("showcase.json must be safe_for_public_portfolio=True")
    if manifest:
        for flag in ("requires_backend", "requires_api_key", "calls_real_models"):
            if manifest.get(flag) is not False:
                errors.append(f"export-manifest.json must keep {flag}=False")
        downloads = manifest.get("downloads") or []
        if len(downloads) < 4:
            errors.append("export-manifest.json must include downloadable sample artifacts")
        for item in downloads:
            local_uri = str(item.get("local_uri") or "")
            expected_hash = str(item.get("sha256") or "")
            if not local_uri or local_uri.startswith("/") or ".." in local_uri.split("/"):
                errors.append(f"download has unsafe local_uri: {local_uri}")
                continue
            if local_uri in fetched and expected_hash and fetched[local_uri].get("sha256") != expected_hash:
                errors.append(f"download hash mismatch: {local_uri}")
    if visitor:
        for flag in ("requires_backend", "requires_api_key", "calls_real_models"):
            if visitor.get(flag) is not False:
                errors.append(f"visitor guide must keep {flag}=False")
        if len(visitor.get("visitor_route") or []) < 5:
            errors.append("visitor guide must include a reviewer route")
    if claim:
        if claim.get("claim_level") != "demo_structure_only":
            errors.append("comic claim report must remain demo_structure_only on public showcase")
        if claim.get("can_claim_real_quality") is not False:
            errors.append("public showcase must not claim real model image quality")

    return {
        "status": "passed" if not errors else "failed",
        "mode": "public_no_key_live_showcase",
        "url": base_url,
        "summary": (
            "Live showcase URL is reachable, downloadable, and keeps the no-key public boundary."
            if not errors
            else "Live showcase URL is not ready for public sharing."
        ),
        "checked_files": len(REQUIRED_STATIC_FILES),
        "download_count": len(manifest.get("downloads") or []) if manifest else 0,
        "visitor_step_count": len(visitor.get("visitor_route") or []) if visitor else 0,
        "claim_level": claim.get("claim_level", "") if claim else "",
        "fetched": fetched,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Public Showcase Live Check",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"URL: {payload.get('url')}",
        f"Summary: {payload.get('summary')}",
        "",
        f"- Checked files: {payload.get('checked_files')}",
        f"- Download catalog entries: {payload.get('download_count')}",
        f"- Visitor route steps: {payload.get('visitor_step_count')}",
        f"- Comic claim level: {payload.get('claim_level') or 'unknown'}",
        "",
        "| File | HTTP | Bytes |",
        "| --- | ---: | ---: |",
    ]
    for path, record in (payload.get("fetched") or {}).items():
        lines.append(f"| `{path}` | {record.get('status_code')} | {record.get('bytes')} |")
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify a deployed no-key public showcase URL.")
    parser.add_argument("--url", required=True, help="Public showcase base URL, for example https://www.atticus.asia/three-stooges/")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    try:
        payload = verify_public_showcase_live(args.url, timeout=args.timeout)
    except ValueError as exc:
        payload = {
            "status": "failed",
            "mode": "public_no_key_live_showcase",
            "url": args.url,
            "summary": "Live showcase URL could not be checked.",
            "checked_files": 0,
            "download_count": 0,
            "visitor_step_count": 0,
            "claim_level": "",
            "fetched": {},
            "errors": [str(exc)],
        }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
