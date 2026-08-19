"""Verify the no-key first-run guide API contract."""

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


EXPECTED_PATHS = {"public_demo", "local_real_use", "developer_extension"}


def verify_first_run_guide_contract() -> dict[str, Any]:
    client = TestClient(app)
    response = client.get("/api/first-run-guide")
    errors: list[str] = []

    if response.status_code != 200:
        errors.append(f"/api/first-run-guide returned {response.status_code}")
        payload: dict[str, Any] = {}
    else:
        payload = response.json()

    if payload.get("status") != "ready":
        errors.append("status must be ready")
    if payload.get("mode") != "guided_first_run":
        errors.append("mode must be guided_first_run")
    if payload.get("public_safe") is not True:
        errors.append("public_safe must be true")
    if payload.get("requires_model_credentials") is not False:
        errors.append("top-level guide must not require model credentials")
    if payload.get("calls_real_models") is not False:
        errors.append("top-level guide must not call real models")

    paths = payload.get("paths") or []
    path_ids = {item.get("id") for item in paths}
    if path_ids != EXPECTED_PATHS:
        errors.append(f"paths must be {sorted(EXPECTED_PATHS)}")

    by_id = {item.get("id"): item for item in paths}
    public_demo = by_id.get("public_demo") or {}
    local_real_use = by_id.get("local_real_use") or {}
    developer_extension = by_id.get("developer_extension") or {}

    if public_demo.get("requires_model_credentials") is not False:
        errors.append("public_demo must not require model credentials")
    if public_demo.get("calls_real_models") is not False:
        errors.append("public_demo must not call real models")
    if local_real_use.get("requires_model_credentials") is not True:
        errors.append("local_real_use must clearly require model credentials")
    if local_real_use.get("calls_real_models") is not True:
        errors.append("local_real_use must clearly call real models")
    if developer_extension.get("requires_model_credentials") is not False:
        errors.append("developer_extension should start from no-key governance checks")

    for item in paths:
        if len(item.get("first_actions") or []) < 3:
            errors.append(f"{item.get('id')} must provide at least three first actions")
        if len(item.get("evidence") or []) < 2:
            errors.append(f"{item.get('id')} must provide at least two evidence links")

    quick_checks = payload.get("quick_checks") or []
    quick_ids = {item.get("id") for item in quick_checks}
    for check_id in ("runtime_health", "local_doctor", "model_guidance", "onboarding_packet", "release_gate"):
        if check_id not in quick_ids:
            errors.append(f"quick_checks must include {check_id}")

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in ("secret", "password", "sk-", "config.yaml contents"):
        if forbidden in serialized:
            errors.append(f"first-run guide must not expose {forbidden}")

    return {
        "status": "passed" if not errors else "failed",
        "mode": "first_run_guide_contract",
        "endpoint": "/api/first-run-guide",
        "path_count": len(paths),
        "quick_check_count": len(quick_checks),
        "paths": sorted(path_ids),
        "public_safe": payload.get("public_safe") is True,
        "requires_model_credentials": payload.get("requires_model_credentials") is True,
        "calls_real_models": payload.get("calls_real_models") is True,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-run Guide Contract",
        "",
        f"Status: `{payload['status']}`",
        f"Endpoint: `{payload['endpoint']}`",
        f"Paths: `{payload.get('path_count', 0)}`",
        f"Quick checks: `{payload.get('quick_check_count', 0)}`",
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

    payload = verify_first_run_guide_contract()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
