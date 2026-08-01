"""Verify public GitHub Actions evidence for the no-key release gate.

This verifier uses GitHub's public REST API for a public repository. It does
not need gh auth, GitHub tokens, model API keys, local config, cookies, or
workspace data.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_REPO = "atticus-zhou/sangechoupijiang"
DEFAULT_BRANCH = "codex/comic-quality-overhaul"
DEFAULT_WORKFLOW = "Release readiness"
DEFAULT_ARTIFACT = "no-key-release-evidence"
REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "release-readiness.yml"
README_FILE = REPO_ROOT / "README.md"
PUBLIC_HANDOFF_FILE = REPO_ROOT / "docs" / "PUBLIC_RELEASE_HANDOFF.md"


def _fetch_json(url: str, *, timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "three-cobblers-github-release-evidence/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"GitHub API request timed out: {exc}") from exc


def _fetch_text(url: str, *, timeout: float) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html",
            "User-Agent": "three-cobblers-github-release-evidence/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"GitHub Actions page returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub Actions page request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"GitHub Actions page request timed out: {exc}") from exc


def _actions_page_url(owner_repo: str, branch: str) -> str:
    return f"https://github.com/{owner_repo}/actions?query=branch%3A{quote(branch, safe='')}"


def _commit_checks_url(owner_repo: str, head_sha: str) -> str:
    return f"https://github.com/{owner_repo}/commit/{quote(head_sha, safe='')}/checks"


def _first_match(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return html.unescape(match.group(1)).strip() if match else default


def _parse_public_actions_html(
    html_text: str,
    *,
    owner_repo: str,
    branch: str,
    workflow_name: str,
) -> dict[str, Any]:
    decoded = html.unescape(html_text)
    run_pattern = re.compile(
        rf'href="/{re.escape(owner_repo)}/actions/runs/(\d+)"',
        flags=re.IGNORECASE,
    )
    candidates: list[dict[str, Any]] = []
    for match in run_pattern.finditer(decoded):
        start = max(0, match.start() - 2500)
        end = min(len(decoded), match.end() + 2500)
        context = decoded[start:end]
        if workflow_name not in context:
            continue

        lower_context = context.lower()
        status = ""
        conclusion = None
        if any(marker in lower_context for marker in ("in_progress", "in progress", "queued", "requested")):
            status = "in_progress"
        elif any(marker in lower_context for marker in ("completed", "success", "failure", "cancelled")):
            status = "completed"

        if "success" in lower_context:
            conclusion = "success"
        elif "failure" in lower_context:
            conclusion = "failure"
        elif "cancelled" in lower_context or "canceled" in lower_context:
            conclusion = "cancelled"

        run_number = _first_match(r"Run\s+(\d+)\s+of\s+", context)
        title = _first_match(r'aria-label="[^"]*?Release readiness\.?\s*([^"]*?)"', context)
        if not title:
            title = _first_match(r'title="([^"]+)"', context)
        if not title:
            title = _first_match(r'<span[^>]*class="[^"]*css-truncate-target[^"]*"[^>]*>\s*([^<]+)', context)

        sha = _first_match(r"\b([0-9a-f]{7,40})\b", context)
        candidates.append(
            {
                "run_number": int(run_number) if str(run_number).isdigit() else None,
                "run_id": match.group(1),
                "display_title": title,
                "head_sha": sha,
                "status": status or "unknown_from_html",
                "conclusion": conclusion,
                "html_url": f"https://github.com/{owner_repo}/actions/runs/{match.group(1)}",
                "created_at": "",
                "updated_at": "",
                "branch": branch,
            }
        )

    if not candidates:
        return {}
    return candidates[0]


def _parse_public_commit_checks_html(
    html_text: str,
    *,
    owner_repo: str,
    branch: str,
    workflow_name: str,
    head_sha: str,
) -> dict[str, Any]:
    decoded = html.unescape(html_text)
    workflow_match = re.search(
        rf'href="/{re.escape(owner_repo)}/actions/runs/(\d+)"[^>]*>\s*<span>\s*{re.escape(workflow_name)}\s*</span>',
        decoded,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not workflow_match:
        return {}

    run_id = workflow_match.group(1)
    context_start = max(0, workflow_match.start() - 4500)
    context_end = min(len(decoded), workflow_match.end() + 6500)
    context = decoded[context_start:context_end]
    lower_context = context.lower()
    job_succeeded = "this job succeeded" in lower_context or "succeeded" in lower_context
    job_failed = "this job failed" in lower_context or "failed" in lower_context
    in_progress = any(marker in lower_context for marker in ("in progress", "queued", "requested", "waiting"))
    title = _first_match(r"<title>\s*([^·<]+)", decoded)
    if not title:
        title = _first_match(r"<h1[^>]*>\s*([^<]+)", decoded)
    job_url = _first_match(
        rf'href="(/{re.escape(owner_repo)}/actions/runs/{re.escape(run_id)}/job/\d+)"',
        context,
    )

    status = "completed" if job_succeeded or job_failed else ("in_progress" if in_progress else "unknown_from_html")
    conclusion = "success" if job_succeeded else ("failure" if job_failed else None)
    return {
        "run_number": None,
        "run_id": run_id,
        "display_title": title,
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "html_url": f"https://github.com/{owner_repo}/actions/runs/{run_id}",
        "job_url": f"https://github.com{job_url}" if job_url else "",
        "created_at": "",
        "updated_at": "",
        "branch": branch,
    }


def _html_fallback_payload(
    *,
    repo: str,
    branch: str,
    workflow_name: str,
    artifact_name: str,
    timeout: float,
    api_error: str,
    head_sha: str = "",
) -> dict[str, Any]:
    owner_repo = repo.strip("/")
    public_url = _actions_page_url(owner_repo, branch)
    errors = [api_error, "GitHub API unavailable; used the public Actions page as a read-only fallback."]
    try:
        html_text = _fetch_text(public_url, timeout=timeout)
    except RuntimeError as exc:
        errors.append(str(exc))
        return _failed_payload(
            repo,
            branch,
            workflow_name,
            artifact_name,
            errors,
            verification_source="github_api_unavailable",
            public_actions_url=public_url,
        )

    latest = _parse_public_actions_html(
        html_text,
        owner_repo=owner_repo,
        branch=branch,
        workflow_name=workflow_name,
    )
    verification_source = "github_actions_html_fallback"
    commit_checks_url = _commit_checks_url(owner_repo, head_sha) if head_sha else ""
    if head_sha:
        try:
            checks_html = _fetch_text(commit_checks_url, timeout=timeout)
            commit_latest = _parse_public_commit_checks_html(
                checks_html,
                owner_repo=owner_repo,
                branch=branch,
                workflow_name=workflow_name,
                head_sha=head_sha,
            )
            if commit_latest:
                latest = commit_latest
                verification_source = "github_commit_checks_html_fallback"
            else:
                errors.append(f"public commit checks page did not expose {workflow_name!r} for {head_sha}")
        except RuntimeError as exc:
            errors.append(str(exc))

    if not latest:
        errors.append(f"public Actions page did not expose a run for {workflow_name!r} on branch {branch!r}")
    else:
        if latest.get("status") != "completed":
            errors.append(f"latest workflow run appears {latest.get('status')}, not completed")
        if latest.get("conclusion") not in (None, "success"):
            errors.append(f"latest workflow conclusion appears {latest.get('conclusion')}, not success")

    errors.append(f"required artifact {artifact_name!r} could not be verified without the GitHub API")
    return {
        "status": "failed",
        "mode": "github_no_key_release_evidence",
        "verification_source": verification_source,
        "repo": owner_repo,
        "branch": branch,
        "workflow_name": workflow_name,
        "artifact_name": artifact_name,
        "public_actions_url": public_url,
        "public_commit_checks_url": commit_checks_url,
        "latest_run": latest,
        "artifact": {},
        "summary": (
            "GitHub API was unavailable. The public Actions page was checked, "
            "but the release evidence artifact still needs API verification."
        ),
        "errors": errors,
    }


def verify_github_release_evidence(
    *,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    workflow_name: str = DEFAULT_WORKFLOW,
    artifact_name: str = DEFAULT_ARTIFACT,
    timeout: float = 20.0,
    head_sha: str = "",
) -> dict[str, Any]:
    errors: list[str] = []
    owner_repo = repo.strip("/")
    if "/" not in owner_repo:
        return _failed_payload(repo, branch, workflow_name, artifact_name, ["repo must use owner/name format"])

    runs_url = (
        f"https://api.github.com/repos/{owner_repo}/actions/runs"
        f"?branch={quote(branch)}&per_page=10"
    )
    try:
        runs_payload = _fetch_json(runs_url, timeout=timeout)
    except RuntimeError as exc:
        return _html_fallback_payload(
            repo=repo,
            branch=branch,
            workflow_name=workflow_name,
            artifact_name=artifact_name,
            timeout=timeout,
            api_error=str(exc),
            head_sha=head_sha,
        )

    runs = [
        run for run in (runs_payload.get("workflow_runs") or [])
        if str(run.get("name") or "") == workflow_name
    ]
    latest = runs[0] if runs else {}
    if not latest:
        errors.append(f"no workflow run found for {workflow_name!r} on branch {branch!r}")
        artifacts = []
    else:
        if latest.get("status") != "completed":
            errors.append(f"latest workflow run is {latest.get('status')}, not completed")
        if latest.get("conclusion") != "success":
            errors.append(f"latest workflow conclusion is {latest.get('conclusion')}, not success")
        artifacts_url = str(latest.get("artifacts_url") or "")
        if not artifacts_url:
            errors.append("latest workflow run does not expose artifacts_url")
            artifacts = []
        else:
            try:
                artifacts_payload = _fetch_json(artifacts_url, timeout=timeout)
                artifacts = artifacts_payload.get("artifacts") or []
            except RuntimeError as exc:
                errors.append(str(exc))
                artifacts = []

    matching_artifacts = [item for item in artifacts if item.get("name") == artifact_name]
    artifact = matching_artifacts[0] if matching_artifacts else {}
    if not artifact:
        errors.append(f"required artifact {artifact_name!r} was not found")
    else:
        if artifact.get("expired") is True:
            errors.append(f"required artifact {artifact_name!r} is expired")
        if int(artifact.get("size_in_bytes") or 0) <= 0:
            errors.append(f"required artifact {artifact_name!r} is empty")

    return {
        "status": "passed" if not errors else "failed",
        "mode": "github_no_key_release_evidence",
        "verification_source": "github_api",
        "repo": owner_repo,
        "branch": branch,
        "workflow_name": workflow_name,
        "artifact_name": artifact_name,
        "public_actions_url": _actions_page_url(owner_repo, branch),
        "public_commit_checks_url": _commit_checks_url(owner_repo, head_sha) if head_sha else "",
        "latest_run": {
            "run_number": latest.get("run_number"),
            "display_title": latest.get("display_title", ""),
            "head_sha": latest.get("head_sha", ""),
            "status": latest.get("status", ""),
            "conclusion": latest.get("conclusion"),
            "html_url": latest.get("html_url", ""),
            "created_at": latest.get("created_at", ""),
            "updated_at": latest.get("updated_at", ""),
        },
        "artifact": {
            "name": artifact.get("name", ""),
            "size_in_bytes": artifact.get("size_in_bytes", 0),
            "expired": artifact.get("expired"),
            "created_at": artifact.get("created_at", ""),
            "archive_download_url": artifact.get("archive_download_url", ""),
        },
        "summary": (
            "Latest public GitHub release-readiness run succeeded and uploaded no-key evidence."
            if not errors
            else "GitHub release evidence is not ready yet."
        ),
        "errors": errors,
    }


def verify_github_release_contract() -> dict[str, Any]:
    """Verify the local no-key GitHub evidence contract without network access."""
    checks: list[dict[str, Any]] = []
    checks.extend(
        [
            _contract_check(
                "workflow_uploads_evidence",
                WORKFLOW_FILE,
                [
                    "name: Release readiness",
                    "branches:",
                    "main",
                    "\"codex/**\"",
                    "permissions:",
                    "contents: read",
                    "python scripts/verify_release_readiness.py --format markdown",
                    "python scripts/check_no_secrets.py",
                    "actions/upload-artifact@v4",
                    f"name: {DEFAULT_ARTIFACT}",
                    "if-no-files-found: error",
                ],
            ),
            _contract_check(
                "readme_explains_github_evidence_boundary",
                README_FILE,
                [
                    "GitHub Actions",
                    "Release readiness",
                    "python scripts/verify_github_release_evidence.py --format markdown",
                    DEFAULT_ARTIFACT,
                    "github_actions_html_fallback",
                    "github_commit_checks_html_fallback",
                    "不证明个人网站线上 Vercel 已经刷新",
                    "npm run check:online",
                ],
            ),
            _contract_check(
                "handoff_explains_github_evidence_boundary",
                PUBLIC_HANDOFF_FILE,
                [
                    "GitHub Actions",
                    "Release readiness",
                    "python scripts/verify_github_release_evidence.py --format markdown",
                    DEFAULT_ARTIFACT,
                    "GitHub 公共 API",
                    "github_actions_html_fallback",
                    "github_commit_checks_html_fallback",
                    "npm run check:online",
                ],
            ),
        ]
    )
    failures = [item["id"] for item in checks if item["status"] != "passed"]
    return {
        "status": "passed" if not failures else "failed",
        "mode": "github_no_key_release_contract",
        "repo": DEFAULT_REPO,
        "branch": DEFAULT_BRANCH,
        "workflow_name": DEFAULT_WORKFLOW,
        "artifact_name": DEFAULT_ARTIFACT,
        "checks": checks,
        "failures": failures,
        "summary": (
            "Local GitHub release evidence contract is documented and wired to CI."
            if not failures
            else f"{len(failures)} local GitHub release evidence contract checks failed."
        ),
    }


def _contract_check(check_id: str, path: Path, markers: list[str]) -> dict[str, Any]:
    relative = path.relative_to(REPO_ROOT).as_posix()
    if not path.exists():
        return {
            "id": check_id,
            "status": "failed",
            "file": relative,
            "missing_file": relative,
            "missing_markers": markers,
        }
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [marker for marker in markers if marker not in text]
    return {
        "id": check_id,
        "status": "passed" if not missing else "failed",
        "file": relative,
        "missing_file": "",
        "missing_markers": missing,
    }


def _failed_payload(
    repo: str,
    branch: str,
    workflow_name: str,
    artifact_name: str,
    errors: list[str],
    *,
    verification_source: str = "github_api",
    public_actions_url: str = "",
    public_commit_checks_url: str = "",
) -> dict[str, Any]:
    return {
        "status": "failed",
        "mode": "github_no_key_release_evidence",
        "verification_source": verification_source,
        "repo": repo,
        "branch": branch,
        "workflow_name": workflow_name,
        "artifact_name": artifact_name,
        "public_actions_url": public_actions_url,
        "public_commit_checks_url": public_commit_checks_url,
        "latest_run": {},
        "artifact": {},
        "summary": "GitHub release evidence is not ready yet.",
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    if payload.get("mode") == "github_no_key_release_contract":
        return _format_contract_markdown(payload)
    run = payload.get("latest_run") or {}
    artifact = payload.get("artifact") or {}
    lines = [
        "# GitHub Release Evidence Check",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Verification source: `{payload.get('verification_source') or '-'}`",
        f"Repository: `{payload.get('repo')}`",
        f"Branch: `{payload.get('branch')}`",
        f"Public Actions URL: {payload.get('public_actions_url') or '-'}",
        f"Public Commit Checks URL: {payload.get('public_commit_checks_url') or '-'}",
        f"Summary: {payload.get('summary')}",
        "",
        "## Latest Run",
        "",
        f"- Workflow: `{payload.get('workflow_name')}`",
        f"- Run: `{run.get('run_number') or '-'}`",
        f"- Title: {run.get('display_title') or '-'}",
        f"- Status: `{run.get('status') or '-'}`",
        f"- Conclusion: `{run.get('conclusion') or '-'}`",
        f"- URL: {run.get('html_url') or '-'}",
        "",
        "## Evidence Artifact",
        "",
        f"- Name: `{artifact.get('name') or '-'}`",
        f"- Size: `{artifact.get('size_in_bytes') or 0}` bytes",
        f"- Expired: `{artifact.get('expired')}`",
        f"- Created: `{artifact.get('created_at') or '-'}`",
    ]
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    return "\n".join(lines) + "\n"


def _format_contract_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# GitHub Release Evidence Contract",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Repository: `{payload.get('repo')}`",
        f"Branch: `{payload.get('branch')}`",
        f"Workflow: `{payload.get('workflow_name')}`",
        f"Artifact: `{payload.get('artifact_name')}`",
        f"Summary: {payload.get('summary')}",
        "",
        "| Check | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for item in payload.get("checks", []):
        lines.append(f"| {item.get('id')} | {item.get('status')} | `{item.get('file')}` |")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for item in payload.get("checks", []):
            if item.get("status") == "passed":
                continue
            lines.append(
                f"- {item.get('id')}: missing_file={item.get('missing_file')}; "
                f"missing_markers={item.get('missing_markers')}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify public GitHub release evidence.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository in owner/name format.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to inspect.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow display name.")
    parser.add_argument("--artifact", default=DEFAULT_ARTIFACT, help="Required artifact name.")
    parser.add_argument("--head-sha", default="", help="Optional commit SHA used for public commit-checks HTML fallback.")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--contract-only", action="store_true", help="Verify local workflow/docs contract without network access.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    if args.contract_only:
        payload = verify_github_release_contract()
    else:
        payload = verify_github_release_evidence(
            repo=args.repo,
            branch=args.branch,
            workflow_name=args.workflow,
            artifact_name=args.artifact,
            timeout=args.timeout,
            head_sha=args.head_sha,
        )
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload), end="")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
