"""Run the post-change development checklist for this repository."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, check_id: str, title: str) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "id": check_id,
        "title": title,
        "command": _display_command(command),
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "summary": _summarize(check_id, stdout, stderr, completed.returncode),
        "stdout_tail": "\n".join(stdout.strip().splitlines()[-8:]),
        "stderr_tail": "\n".join(stderr.strip().splitlines()[-8:]),
    }


def _display_command(command: list[str]) -> str:
    display = []
    for part in command:
        if part == sys.executable:
            display.append("python")
        else:
            display.append(part)
    return " ".join(display)


def _summarize(check_id: str, stdout: str, stderr: str, returncode: int) -> str:
    text = stdout.strip() or stderr.strip()
    if check_id == "git_status":
        first = text.splitlines()[0] if text else "no git status output"
        dirty = max(0, len(text.splitlines()) - 1)
        return f"{first}; changed_files={dirty}"
    if stdout.strip().startswith("{"):
        try:
            payload = json.loads(stdout)
            checks = payload.get("checks") or []
            failures = payload.get("failures") or []
            parts = [f"status={payload.get('status')}"]
            if payload.get("mode"):
                parts.append(f"mode={payload.get('mode')}")
            if checks:
                parts.append(f"checks={len(checks)}")
            if failures is not None:
                parts.append(f"failures={len(failures)}")
            return "; ".join(parts)
        except json.JSONDecodeError:
            pass
    if check_id == "unit_tests":
        return "all tests passed" if returncode == 0 else "unit tests failed"
    if returncode == 0:
        return text.splitlines()[-1] if text else "passed"
    return text.splitlines()[-1] if text else "failed"


def verify_development_checklist(*, run_tests: bool, require_clean: bool, skip_release: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(_run(["git", "status", "--short", "--branch"], check_id="git_status", title="Git status"))
    checks.append(_run(["git", "diff", "--check"], check_id="diff_check", title="Whitespace diff check"))
    checks.append(_run([sys.executable, "scripts/check_no_secrets.py"], check_id="secret_scan", title="Secret and runtime artifact scan"))
    checks.append(_run([sys.executable, "scripts/verify_office_isolation.py", "--format", "json"], check_id="office_isolation", title="Office isolation"))
    if skip_release:
        checks.append({
            "id": "release_readiness",
            "title": "Release readiness",
            "command": "python scripts/verify_release_readiness.py --format json",
            "status": "skipped",
            "returncode": 0,
            "summary": "skipped by --skip-release",
            "stdout_tail": "",
            "stderr_tail": "",
        })
    else:
        checks.append(_run(
            [sys.executable, "scripts/verify_release_readiness.py", "--format", "json"],
            check_id="release_readiness",
            title="Release readiness",
        ))
    if run_tests:
        checks.append(_run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
            check_id="unit_tests",
            title="Full unit test suite",
        ))
    else:
        checks.append({
            "id": "unit_tests",
            "title": "Full unit test suite",
            "command": "python -m unittest discover -s tests -q",
            "status": "skipped",
            "returncode": 0,
            "summary": "skipped; pass --run-tests before public handoff or broad refactors",
            "stdout_tail": "",
            "stderr_tail": "",
        })

    dirty_files = _changed_file_count(checks[0])
    clean_ok = not require_clean or dirty_files == 0
    failures = [item["id"] for item in checks if item["status"] == "failed"]
    if not clean_ok:
        failures.append("working_tree_not_clean")
    return {
        "status": "passed" if not failures else "failed",
        "mode": "development_post_change_checklist",
        "require_clean": require_clean,
        "run_tests": run_tests,
        "skip_release": skip_release,
        "changed_files": dirty_files,
        "checks": checks,
        "failures": failures,
        "next_action": _next_action(failures, run_tests, require_clean),
    }


def _changed_file_count(git_status_check: dict[str, Any]) -> int:
    summary = str(git_status_check.get("summary") or "")
    marker = "changed_files="
    if marker not in summary:
        return 0
    try:
        return int(summary.split(marker, 1)[1].split(";", 1)[0])
    except ValueError:
        return 0


def _next_action(failures: list[str], run_tests: bool, require_clean: bool) -> str:
    if failures:
        if "working_tree_not_clean" in failures:
            return "Review, commit, or intentionally leave the listed working-tree changes before handoff."
        return "Open the failed check output, fix the blocking issue, then rerun this checklist."
    if not run_tests:
        return "For a public handoff or broad refactor, rerun with --run-tests."
    if not require_clean:
        return "For final handoff, rerun with --require-clean after committing intended changes."
    return "Development checklist is clean for public handoff."


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Development Checklist Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Changed files: `{payload.get('changed_files')}`",
        f"Run tests: `{payload.get('run_tests')}`",
        f"Require clean: `{payload.get('require_clean')}`",
        f"Next action: {payload.get('next_action')}",
        "",
        "| Check | Status | Summary | Command |",
        "| --- | --- | --- | --- |",
    ]
    for check in payload.get("checks", []):
        summary = str(check.get("summary", "")).replace("|", "/")
        lines.append(f"| {check.get('title')} | {check.get('status')} | {summary} | `{check.get('command')}` |")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for check in payload.get("checks", []):
            if check.get("status") != "failed":
                continue
            lines.append(f"### {check.get('id')}")
            if check.get("stdout_tail"):
                lines.extend(["", "stdout:", "```", check["stdout_tail"], "```"])
            if check.get("stderr_tail"):
                lines.extend(["", "stderr:", "```", check["stderr_tail"], "```"])
        for failure in payload.get("failures", []):
            if failure == "working_tree_not_clean":
                lines.append("- working_tree_not_clean")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run the repository development checklist.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--run-tests", action="store_true", help="Also run python -m unittest discover -s tests -q.")
    parser.add_argument("--require-clean", action="store_true", help="Fail when the working tree has uncommitted changes.")
    parser.add_argument("--skip-release", action="store_true", help="Skip the full release gate for fast script tests.")
    args = parser.parse_args()

    payload = verify_development_checklist(
        run_tests=args.run_tests,
        require_clean=args.require_clean,
        skip_release=args.skip_release,
    )
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload), end="")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
