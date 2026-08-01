"""Verify public GitHub Actions evidence for the no-key release gate.

This verifier uses GitHub's public REST API for a public repository. It does
not need gh auth, GitHub tokens, model API keys, local config, cookies, or
workspace data.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_REPO = "atticus-zhou/sangechoupijiang"
DEFAULT_BRANCH = "codex/comic-quality-overhaul"
DEFAULT_WORKFLOW = "Release readiness"
DEFAULT_ARTIFACT = "no-key-release-evidence"


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


def verify_github_release_evidence(
    *,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    workflow_name: str = DEFAULT_WORKFLOW,
    artifact_name: str = DEFAULT_ARTIFACT,
    timeout: float = 20.0,
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
        return _failed_payload(repo, branch, workflow_name, artifact_name, [str(exc)])

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
        "repo": owner_repo,
        "branch": branch,
        "workflow_name": workflow_name,
        "artifact_name": artifact_name,
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


def _failed_payload(
    repo: str,
    branch: str,
    workflow_name: str,
    artifact_name: str,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "status": "failed",
        "mode": "github_no_key_release_evidence",
        "repo": repo,
        "branch": branch,
        "workflow_name": workflow_name,
        "artifact_name": artifact_name,
        "latest_run": {},
        "artifact": {},
        "summary": "GitHub release evidence is not ready yet.",
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    run = payload.get("latest_run") or {}
    artifact = payload.get("artifact") or {}
    lines = [
        "# GitHub Release Evidence Check",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Repository: `{payload.get('repo')}`",
        f"Branch: `{payload.get('branch')}`",
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


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify public GitHub release evidence.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository in owner/name format.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to inspect.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow display name.")
    parser.add_argument("--artifact", default=DEFAULT_ARTIFACT, help="Required artifact name.")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = verify_github_release_evidence(
        repo=args.repo,
        branch=args.branch,
        workflow_name=args.workflow,
        artifact_name=args.artifact,
        timeout=args.timeout,
    )
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload), end="")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
