"""Verify the public-safe FastAPI health endpoint contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.web.app import app


def verify_runtime_health_contract() -> dict[str, Any]:
    client = TestClient(app)
    root_response = client.get("/health")
    alias_response = client.get("/api/health")
    errors: list[str] = []

    if root_response.status_code != 200:
        errors.append(f"/health returned {root_response.status_code}")
        payload: dict[str, Any] = {}
    else:
        payload = root_response.json()

    if alias_response.status_code != 200:
        errors.append(f"/api/health returned {alias_response.status_code}")
        alias_payload: dict[str, Any] = {}
    else:
        alias_payload = alias_response.json()

    if payload != alias_payload:
        errors.append("/api/health must match /health exactly")

    required_values = {
        "status": "ok",
        "service": "sangechoupijiang",
        "public_safe": True,
        "requires_model_credentials": False,
        "calls_real_models": False,
    }
    for key, expected in required_values.items():
        if payload.get(key) != expected:
            errors.append(f"{key} must be {expected!r}")

    office_ids = payload.get("office_ids") or []
    for office_id in ("research", "comic_production"):
        if office_id not in office_ids:
            errors.append(f"office_ids must include {office_id}")

    checks = payload.get("checks") or {}
    for check_id, endpoint in {
        "offices": "/api/offices",
        "system_preflight": "/api/system/preflight",
        "office_protocols": "/api/offices/protocols",
    }.items():
        if checks.get(check_id) != endpoint:
            errors.append(f"checks.{check_id} must point to {endpoint}")

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in ("api_key", "secret", "password", "config.yaml"):
        if forbidden in serialized:
            errors.append(f"health payload must not expose {forbidden}")

    return {
        "status": "passed" if not errors else "failed",
        "mode": "runtime_health_contract",
        "endpoint": "/health",
        "alias": "/api/health",
        "service": payload.get("service", ""),
        "office_count": payload.get("office_count", 0),
        "office_ids": office_ids,
        "public_safe": payload.get("public_safe") is True,
        "requires_model_credentials": payload.get("requires_model_credentials") is True,
        "calls_real_models": payload.get("calls_real_models") is True,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Runtime Health Contract",
        "",
        f"Status: `{payload['status']}`",
        f"Endpoint: `{payload['endpoint']}`",
        f"Alias: `{payload['alias']}`",
        f"Service: `{payload.get('service', '')}`",
        f"Office count: `{payload.get('office_count', 0)}`",
        f"Public safe: `{payload.get('public_safe')}`",
        f"Requires model credentials: `{payload.get('requires_model_credentials')}`",
        f"Calls real models: `{payload.get('calls_real_models')}`",
    ]
    if payload.get("errors"):
        lines.extend(["", "## Errors"])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    payload = verify_runtime_health_contract()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
