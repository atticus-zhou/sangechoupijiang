"""Diagnose GitHub Actions emails for the public showcase fallback.

This command answers a narrow operator question:

"A GitHub email says Public showcase pages failed. Does that mean the current
Three Cobblers product is broken?"

It uses only public GitHub metadata and the local workflow contract. It does
not need GitHub auth, model API keys, cookies, Vercel tokens, or local user
outputs.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_REPO = "atticus-zhou/sangechoupijiang"
DEFAULT_BRANCH = "main"
DEFAULT_WORKFLOW = "Public showcase pages"
REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "pages-showcase.yml"


def _fetch_json(url: str, *, timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "three-cobblers-showcase-email-diagnosis/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"GitHub API request timed out: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc}") from exc


def _local_head_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def _expand_local_head_sha(head_sha: str) -> str:
    value = (head_sha or "").strip()
    if not value or len(value) >= 40:
        return value
    try:
        completed = subprocess.run(
            ["git", "rev-parse", value],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return value
    expanded = completed.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", expanded, flags=re.IGNORECASE):
        return expanded
    return value


def _read_workflow_contract() -> dict[str, Any]:
    text = WORKFLOW_FILE.read_text(encoding="utf-8") if WORKFLOW_FILE.exists() else ""
    has_workflow_dispatch = "workflow_dispatch:" in text
    has_push_trigger = bool(re.search(r"(?m)^\s{2}push:\s*$|^push:\s*$", text))
    return {
        "workflow_file": str(WORKFLOW_FILE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "exists": WORKFLOW_FILE.exists(),
        "has_workflow_dispatch": has_workflow_dispatch,
        "has_push_trigger": has_push_trigger,
        "manual_only": has_workflow_dispatch and not has_push_trigger,
    }


def _short_sha(value: str) -> str:
    return value[:7] if value else ""


def _same_commit(left: str, right: str) -> bool:
    if not left or not right:
        return False
    left = left.lower()
    right = right.lower()
    return left == right or left.startswith(right) or right.startswith(left)


def _normalize_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": run.get("id"),
        "name": run.get("name") or "",
        "head_sha": run.get("head_sha") or "",
        "head_sha_short": _short_sha(str(run.get("head_sha") or "")),
        "event": run.get("event") or "",
        "status": run.get("status") or "",
        "conclusion": run.get("conclusion"),
        "created_at": run.get("created_at") or "",
        "updated_at": run.get("updated_at") or "",
        "html_url": run.get("html_url") or "",
        "display_title": run.get("display_title") or "",
    }


def _fetch_workflow_runs(
    *,
    repo: str,
    branch: str,
    workflow_name: str,
    timeout: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    workflows_url = f"https://api.github.com/repos/{repo}/actions/workflows"
    workflows_payload = _fetch_json(workflows_url, timeout=timeout)
    workflow = next(
        (
            item
            for item in workflows_payload.get("workflows", [])
            if (item.get("name") or "") == workflow_name
        ),
        {},
    )
    if workflow.get("id"):
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow['id']}/runs?branch={branch}&per_page=30"
    else:
        warnings.append(f"Workflow {workflow_name!r} was not found in the public workflows list; falling back to repository runs.")
        url = f"https://api.github.com/repos/{repo}/actions/runs?branch={branch}&per_page=30"
    payload = _fetch_json(url, timeout=timeout)
    runs = [
        _normalize_run(run)
        for run in payload.get("workflow_runs", [])
        if (run.get("name") or "") == workflow_name
    ]
    if not runs:
        warnings.append(f"No recent runs named {workflow_name!r} were found on branch {branch!r}.")
    return runs, warnings


def diagnose_showcase_workflow_email(
    *,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    workflow_name: str = DEFAULT_WORKFLOW,
    head_sha: str = "",
    timeout: float = 20.0,
    contract_only: bool = False,
) -> dict[str, Any]:
    contract = _read_workflow_contract()
    local_head = _local_head_sha()
    expanded_head = _expand_local_head_sha(head_sha)
    warnings: list[str] = []
    errors: list[str] = []

    runs: list[dict[str, Any]] = []
    if not contract_only:
        try:
            runs, warnings = _fetch_workflow_runs(
                repo=repo,
                branch=branch,
                workflow_name=workflow_name,
                timeout=timeout,
            )
        except RuntimeError as exc:
            errors.append(str(exc))

    matched_run = {}
    if expanded_head:
        matched_run = next((run for run in runs if _same_commit(run.get("head_sha", ""), expanded_head)), {})

    latest_run = runs[0] if runs else {}
    failed_runs = [run for run in runs if run.get("conclusion") == "failure"]
    current_failure = next((run for run in failed_runs if _same_commit(run.get("head_sha", ""), local_head)), {})
    matched_failure = matched_run if matched_run.get("conclusion") == "failure" else {}

    diagnosis = "unknown"
    summary = "Could not determine whether the failed email is current."
    status = "failed"
    if not contract.get("exists"):
        errors.append("Public showcase pages workflow file is missing.")
        diagnosis = "workflow_file_missing"
        summary = "The local Pages fallback workflow file is missing."
    elif contract.get("has_push_trigger"):
        diagnosis = "workflow_still_push_triggered"
        summary = "The Pages fallback workflow can still run on push and may keep sending failure emails."
    elif contract.get("manual_only") and matched_failure and not _same_commit(matched_failure.get("head_sha", ""), local_head):
        diagnosis = "old_failed_run_email"
        summary = "The email points to an older failed run; the current workflow is manual-only and should not fail on every push."
        status = "passed"
    elif contract.get("manual_only") and current_failure:
        diagnosis = "current_manual_run_failed"
        summary = "The latest local commit has a failed manual Pages fallback run. Inspect that run before using the fallback URL."
    elif contract.get("manual_only") and not errors:
        diagnosis = "current_contract_safe"
        summary = "The Pages fallback workflow is manual-only; old failure emails do not prove the current product is broken."
        status = "passed"
    elif errors:
        diagnosis = "github_metadata_unavailable"
        summary = "Local workflow contract was checked, but public GitHub run metadata could not be fetched."
    else:
        status = "passed"

    next_actions = _next_actions(
        diagnosis=diagnosis,
        matched_run=matched_run,
        latest_run=latest_run,
        contract=contract,
    )

    return {
        "status": status,
        "mode": "github_public_showcase_workflow_email_diagnosis",
        "repo": repo,
        "branch": branch,
        "workflow_name": workflow_name,
        "workflow_contract": contract,
        "local_head_sha": local_head,
        "local_head_sha_short": _short_sha(local_head),
        "email_head_sha": expanded_head,
        "email_head_sha_short": _short_sha(expanded_head),
        "diagnosis": diagnosis,
        "summary": summary,
        "latest_run": latest_run,
        "matched_email_run": matched_run,
        "recent_runs": runs[:5],
        "errors": errors,
        "warnings": warnings,
        "next_actions": next_actions,
    }


def _next_actions(
    *,
    diagnosis: str,
    matched_run: dict[str, Any],
    latest_run: dict[str, Any],
    contract: dict[str, Any],
) -> list[str]:
    if diagnosis == "old_failed_run_email":
        return [
            "把这封邮件当作旧提交的失败通知处理；不要因此回滚产品代码。",
            "如果你要使用 GitHub Pages 备用入口，再到仓库 Settings -> Pages 把 Source 设为 GitHub Actions，并手动重跑 Public showcase pages。",
            "真正的个人网站线上入口仍以个人网站仓库的 `npm run check:online` 为准。",
        ]
    if diagnosis == "current_contract_safe":
        return [
            "当前 Pages fallback workflow 只有手动触发；它不会再因为每次 push 自动失败发邮件。",
            "遇到新邮件时，把邮件里的 commit SHA 传给本命令：`python scripts/diagnose_showcase_workflow_email.py --head-sha <commit> --format markdown`。",
            "继续用 `python scripts/verify_release_readiness.py --format markdown` 判断产品本体 release gate。",
        ]
    if diagnosis == "workflow_still_push_triggered":
        return [
            "先把 `.github/workflows/pages-showcase.yml` 改成只保留 `workflow_dispatch`。",
            "不要用 `continue-on-error` 掩盖失败；Pages 未启用时应该给出清楚说明，而不是每次 push 红色失败。",
        ]
    if diagnosis == "current_manual_run_failed":
        run_url = matched_run.get("html_url") or latest_run.get("html_url") or "-"
        return [
            f"打开失败 run 查看具体步骤：{run_url}",
            "如果失败只是 GitHub Pages 未启用，去 Settings -> Pages 设置 Source: GitHub Actions 后手动重跑。",
            "这仍不等同于个人网站 Vercel 入口可用；线上公开链接继续以 `npm run check:online` 为准。",
        ]
    if diagnosis == "workflow_file_missing":
        return ["恢复 `.github/workflows/pages-showcase.yml`，否则 GitHub Pages 备用公开入口不可复现。"]
    return [
        "先查看 errors/warnings；如果只是 GitHub API 暂时不可用，可以稍后重跑。",
        "本命令不需要 API Key；不要为了诊断邮件把任何密钥提交到仓库。",
    ]


def format_markdown(payload: dict[str, Any]) -> str:
    contract = payload.get("workflow_contract") or {}
    latest = payload.get("latest_run") or {}
    matched = payload.get("matched_email_run") or {}
    lines = [
        "# Public Showcase Workflow Email Diagnosis",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Repository: `{payload.get('repo')}`",
        f"Branch: `{payload.get('branch')}`",
        f"Workflow: `{payload.get('workflow_name')}`",
        f"Diagnosis: `{payload.get('diagnosis')}`",
        f"Summary: {payload.get('summary')}",
        "",
        "## Local Workflow Contract",
        "",
        f"- File: `{contract.get('workflow_file') or '-'}`",
        f"- Exists: `{contract.get('exists')}`",
        f"- Manual trigger: `{contract.get('has_workflow_dispatch')}`",
        f"- Push trigger: `{contract.get('has_push_trigger')}`",
        f"- Manual only: `{contract.get('manual_only')}`",
        "",
        "## Commit Context",
        "",
        f"- Local HEAD: `{payload.get('local_head_sha_short') or '-'}`",
        f"- Email SHA: `{payload.get('email_head_sha_short') or '-'}`",
        "",
        "## Latest Public Showcase Run",
        "",
        f"- Run: `{latest.get('id') or '-'}`",
        f"- SHA: `{latest.get('head_sha_short') or '-'}`",
        f"- Event: `{latest.get('event') or '-'}`",
        f"- Status: `{latest.get('status') or '-'}`",
        f"- Conclusion: `{latest.get('conclusion') or '-'}`",
        f"- URL: {latest.get('html_url') or '-'}",
    ]
    if matched:
        lines.extend(
            [
                "",
                "## Matched Email Run",
                "",
                f"- Run: `{matched.get('id') or '-'}`",
                f"- SHA: `{matched.get('head_sha_short') or '-'}`",
                f"- Event: `{matched.get('event') or '-'}`",
                f"- Status: `{matched.get('status') or '-'}`",
                f"- Conclusion: `{matched.get('conclusion') or '-'}`",
                f"- URL: {matched.get('html_url') or '-'}",
            ]
        )
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    if payload.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in payload["warnings"])
    if payload.get("next_actions"):
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {item}" for item in payload["next_actions"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Diagnose GitHub Public showcase pages failure emails.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository in owner/name format.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to inspect.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow display name.")
    parser.add_argument("--head-sha", default="", help="Commit SHA shown in the GitHub failure email.")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--contract-only", action="store_true", help="Check only the local workflow trigger contract.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = diagnose_showcase_workflow_email(
        repo=args.repo,
        branch=args.branch,
        workflow_name=args.workflow,
        head_sha=args.head_sha,
        timeout=args.timeout,
        contract_only=args.contract_only,
    )
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload), end="")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
