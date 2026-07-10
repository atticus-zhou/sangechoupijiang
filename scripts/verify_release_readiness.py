"""Run the public-release readiness gate without real model calls."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


RELEASE_CHECKS = [
    {
        "id": "first_run",
        "title": "First-run guidance",
        "command": ["scripts/verify_first_run_readiness.py", "--format", "json"],
    },
    {
        "id": "public_demo",
        "title": "Public no-key demo",
        "command": ["scripts/verify_public_demo_mode.py", "--format", "json"],
    },
    {
        "id": "comic_delivery",
        "title": "AI comic Word canvas delivery",
        "command": ["scripts/verify_comic_v2_delivery.py", "--format", "json"],
    },
    {
        "id": "research_readiness",
        "title": "Research office staged delivery",
        "command": ["scripts/verify_research_office_readiness.py", "--format", "json"],
    },
    {
        "id": "office_governance",
        "title": "Office extension governance",
        "command": ["scripts/verify_office_extension_governance.py", "--format", "json"],
    },
    {
        "id": "product_readiness",
        "title": "Product readiness with deterministic E2E",
        "command": ["scripts/verify_product_readiness.py", "--format", "json", "--run-e2e"],
    },
    {
        "id": "secret_scan",
        "title": "Secret and runtime artifact scan",
        "command": ["scripts/check_no_secrets.py"],
    },
]


def _run_check(check: dict[str, Any]) -> dict[str, Any]:
    command = [sys.executable, *check["command"]]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    parsed: dict[str, Any] | None = None
    if stdout.strip().startswith("{"):
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "id": check["id"],
        "title": check["title"],
        "command": "python " + " ".join(check["command"]),
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "summary": _summary_for(check["id"], parsed, stdout, stderr),
        "parsed_status": (parsed or {}).get("status", ""),
        "stdout_tail": "\n".join(stdout.strip().splitlines()[-8:]),
        "stderr_tail": "\n".join(stderr.strip().splitlines()[-8:]),
    }


def _summary_for(check_id: str, parsed: dict[str, Any] | None, stdout: str, stderr: str) -> str:
    if parsed:
        if check_id == "public_demo":
            demos = parsed.get("demos") or {}
            return (
                f"{len(demos)} demos; "
                f"showcase={parsed.get('showcase_manifest', {}).get('status_code')}; "
                f"mode={parsed.get('mode')}"
            )
        if check_id == "comic_delivery":
            return (
                f"handoff_ready={parsed.get('handoff_ready')}; "
                f"assets={parsed.get('asset_count')}; "
                f"shots={parsed.get('shot_count')}; "
                f"embedded_images={parsed.get('embedded_images')}"
            )
        if check_id == "research_readiness":
            package = parsed.get("artifact_package") or {}
            quality = package.get("quality") or {}
            return (
                f"quality={quality.get('status')}:{quality.get('score')}; "
                f"downloads={parsed.get('demo_endpoint', {}).get('download_count')}"
            )
        if check_id == "office_governance":
            return (
                f"primary={','.join(parsed.get('primary_office_ids') or [])}; "
                f"offices={len(parsed.get('offices') or [])}"
            )
        if check_id == "product_readiness":
            runtime = parsed.get("runtime_verification") or {}
            stage_b = runtime.get("stage_b_product_loop") or {}
            return f"status={parsed.get('status')}; stage_b={stage_b.get('status')}"
        if check_id == "first_run":
            return (
                f"mode={parsed.get('mode')}; "
                f"paths={','.join(parsed.get('recommended_order') or [])}"
            )
        return str(parsed.get("summary") or parsed.get("status") or "parsed json")
    text = (stdout or stderr).strip()
    return text.splitlines()[-1] if text else "no output"


def verify_release_readiness() -> dict[str, Any]:
    checks = [_run_check(check) for check in RELEASE_CHECKS]
    failures = [item for item in checks if item["status"] != "passed"]
    return {
        "status": "passed" if not failures else "failed",
        "mode": "public_release_readiness",
        "safe_for_public_release": not failures,
        "summary": (
            "All no-key release gates passed."
            if not failures
            else f"{len(failures)} release gates failed."
        ),
        "checks": checks,
        "failures": [item["id"] for item in failures],
        "commands": [item["command"] for item in checks],
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Release Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Safe for public release: `{payload.get('safe_for_public_release')}`",
        f"Summary: {payload.get('summary')}",
        "",
        "| Check | Status | Summary | Command |",
        "| --- | --- | --- | --- |",
    ]
    for check in payload.get("checks", []):
        lines.append(
            f"| {check.get('title')} | {check.get('status')} | "
            f"{str(check.get('summary', '')).replace('|', '/')} | `{check.get('command')}` |"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for check in payload["checks"]:
            if check["status"] == "passed":
                continue
            lines.append(f"### {check['id']}")
            if check.get("stdout_tail"):
                lines.extend(["", "stdout:", "```", check["stdout_tail"], "```"])
            if check.get("stderr_tail"):
                lines.extend(["", "stderr:", "```", check["stderr_tail"], "```"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run public-release readiness gates.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = verify_release_readiness()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
