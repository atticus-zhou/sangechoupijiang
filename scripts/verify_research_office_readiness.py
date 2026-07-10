"""Verify research-office demo and artifact readiness without real model calls."""

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

from src.research_artifacts import build_research_artifacts
from src.research_quality import assess_research_package
from src.web.app import app


REQUIRED_RESEARCH_ARTIFACTS = {
    "report",
    "standard_report",
    "briefing",
    "source_list",
    "data_table",
    "competitor_table",
    "review_pain_points",
    "opportunity_map",
    "chart_plan",
    "screenshot_plan",
}

SCHEMA_GATED_ARTIFACTS = {
    "standard_report": "research_standard_report",
    "source_list": "research_source_list",
    "data_table": "research_data_table",
    "competitor_table": "research_competitor_table",
}


def _load_fixture() -> dict[str, Any]:
    fixture_path = REPO_ROOT / "tests" / "fixtures" / "research_sample.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _verify_artifact_package(errors: list[str]) -> dict[str, Any]:
    result = _load_fixture()
    artifacts = build_research_artifacts("demo_research", result)
    by_type = {item.get("artifact_type"): item for item in artifacts}
    artifact_types = set(by_type)
    missing_artifacts = sorted(REQUIRED_RESEARCH_ARTIFACTS - artifact_types)
    if missing_artifacts:
        errors.append("research package missing artifacts: " + ", ".join(missing_artifacts))

    schema_gates: dict[str, Any] = {}
    for artifact_type, schema_id in SCHEMA_GATED_ARTIFACTS.items():
        artifact = by_type.get(artifact_type) or {}
        schema_gate = (artifact.get("metadata") or {}).get("schema_gate") or {}
        schema_gates[artifact_type] = schema_gate
        if schema_gate.get("schema_id") != schema_id:
            errors.append(f"{artifact_type} did not record schema gate {schema_id}")
        if schema_gate.get("status") != "passed":
            errors.append(f"{artifact_type} schema gate did not pass")

    quality = assess_research_package(artifacts)
    if quality.get("status") != "ready":
        errors.append(f"research quality status is {quality.get('status')}")
    if quality.get("missing_artifacts"):
        errors.append("research quality has missing artifacts")

    screenshot_plan = by_type.get("screenshot_plan", {}).get("content", "")
    source_list = by_type.get("source_list", {}).get("content", "")
    data_table = by_type.get("data_table", {}).get("content", "")
    competitor_table = by_type.get("competitor_table", {}).get("content", "")
    if "evidence_01.png" not in screenshot_plan:
        errors.append("screenshot plan must provide evidence file naming")
    if "http" not in source_list and "local://" not in source_list:
        errors.append("source list must keep URL or pending local evidence references")
    if "|" not in data_table:
        errors.append("data table must be reusable markdown")
    if "|" not in competitor_table:
        errors.append("competitor table must be reusable markdown")

    return {
        "status": "passed" if not missing_artifacts and quality.get("status") == "ready" else "failed",
        "artifact_count": len(artifacts),
        "artifact_types": sorted(artifact_types),
        "missing_artifacts": missing_artifacts,
        "quality": quality,
        "schema_gates": schema_gates,
        "has_screenshot_plan": bool(screenshot_plan),
        "has_source_trace": "http" in source_list or "local://" in source_list,
        "has_data_table": "|" in data_table,
        "has_competitor_table": "|" in competitor_table,
    }


def _download_items(payload: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for item in payload.get("artifacts") or []:
        uri = str(item.get("uri") or "")
        if item.get("status") == "downloadable" and uri.startswith("/api/demo/research/files/"):
            items.append({"title": str(item.get("title") or uri), "uri": uri})
    return items


def _verify_demo_endpoint(errors: list[str]) -> dict[str, Any]:
    client = TestClient(app)
    response = client.get("/api/demo/research")
    if response.status_code != 200:
        errors.append(f"research demo returned {response.status_code}")
        return {"status": "failed", "status_code": response.status_code, "downloads": []}

    payload = response.json()
    if payload.get("mode") != "no_key_demo":
        errors.append("research demo must stay in no_key_demo mode")
    if payload.get("requires_api_key") is not False:
        errors.append("research demo must not require API key")
    if payload.get("calls_real_models") is not False:
        errors.append("research demo must not call real models")

    downloads = []
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
            errors.append(f"research demo download failed: {item['uri']}")
        if record["bytes"] <= 20:
            errors.append(f"research demo download too small: {item['uri']}")

    required_downloads = {
        "/api/demo/research/files/report.md",
        "/api/demo/research/files/evidence_manifest.json",
    }
    present_downloads = {item["uri"] for item in downloads}
    missing_downloads = sorted(required_downloads - present_downloads)
    if missing_downloads:
        errors.append("research demo missing downloads: " + ", ".join(missing_downloads))

    return {
        "status": "passed" if response.status_code == 200 and not missing_downloads else "failed",
        "status_code": response.status_code,
        "mode": payload.get("mode", ""),
        "requires_api_key": bool(payload.get("requires_api_key")),
        "calls_real_models": bool(payload.get("calls_real_models")),
        "download_count": len(downloads),
        "downloads": downloads,
    }


def verify_research_office_readiness() -> dict[str, Any]:
    errors: list[str] = []
    artifact_package = _verify_artifact_package(errors)
    demo_endpoint = _verify_demo_endpoint(errors)
    return {
        "status": "passed" if not errors else "failed",
        "mode": "research_office_no_key_readiness",
        "summary": (
            "Research office can produce a traceable staged research package and public demo downloads."
            if not errors
            else "Research office readiness found gaps."
        ),
        "artifact_package": artifact_package,
        "demo_endpoint": demo_endpoint,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    package = payload.get("artifact_package") or {}
    quality = package.get("quality") or {}
    demo = payload.get("demo_endpoint") or {}
    lines = [
        "# Research Office Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Summary: {payload.get('summary')}",
        "",
        "## Artifact Package",
        "",
        f"- Artifact count: {package.get('artifact_count')}",
        f"- Quality status: {quality.get('status')} ({quality.get('score')})",
        f"- Missing artifacts: {', '.join(package.get('missing_artifacts') or []) or '-'}",
        f"- Screenshot plan: {package.get('has_screenshot_plan')}",
        f"- Source trace: {package.get('has_source_trace')}",
        f"- Data table: {package.get('has_data_table')}",
        f"- Competitor table: {package.get('has_competitor_table')}",
        "",
        "## Schema Gates",
        "",
        "| Artifact | Schema | Status |",
        "| --- | --- | --- |",
    ]
    for artifact_type, gate in (package.get("schema_gates") or {}).items():
        lines.append(
            f"| {artifact_type} | {gate.get('schema_id', '')} | {gate.get('status', '')} |"
        )

    lines.extend(
        [
            "",
            "## Public Demo",
            "",
            f"- HTTP: {demo.get('status_code')}",
            f"- Mode: {demo.get('mode')}",
            f"- Requires API key: {demo.get('requires_api_key')}",
            f"- Calls real models: {demo.get('calls_real_models')}",
            f"- Downloads: {demo.get('download_count')}",
        ]
    )
    for item in demo.get("downloads") or []:
        lines.append(f"  - `{item.get('uri')}`: HTTP {item.get('status_code')}, {item.get('bytes')} bytes")

    if quality.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in quality["warnings"])
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify research-office staged delivery readiness.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = verify_research_office_readiness()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
