"""Export a no-key onboarding packet for people cloning the project from GitHub."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "tmp" / "github-onboarding-packet"
DEFAULT_ZIP = REPO_ROOT / "tmp" / "github-onboarding-packet.zip"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

COPY_FILES = [
    ("START_HERE.md", "START_HERE.md", "Shortest first-run guide for demo viewing, local real use, public deployment, and office development."),
    ("README.md", "README.md", "Main project overview and first-run commands."),
    ("config.example.yaml", "config.example.yaml", "Safe example config; copy locally to config.yaml before real use."),
    ("requirements.txt", "requirements.txt", "Python dependency list."),
    ("docs/FIRST_RUN_DECISION_CARD.md", "docs/FIRST_RUN_DECISION_CARD.md", "Which path to use first: public demo, local real use, or developer extension."),
    ("docs/MODEL_CONFIGURATION.md", "docs/MODEL_CONFIGURATION.md", "Department-by-department model requirements."),
    ("docs/MODEL_CAPABILITY_MATRIX.json", "docs/MODEL_CAPABILITY_MATRIX.json", "Machine-readable model capability matrix."),
    ("docs/DEPLOYMENT_MODES.md", "docs/DEPLOYMENT_MODES.md", "Deployment modes and public/private boundaries."),
    ("docs/STATIC_SHOWCASE_DEPLOYMENT.md", "docs/STATIC_SHOWCASE_DEPLOYMENT.md", "How to export and verify the static no-key showcase."),
    ("docs/PUBLIC_RELEASE_HANDOFF.md", "docs/PUBLIC_RELEASE_HANDOFF.md", "Public release handoff and reviewer boundary."),
    ("docs/REAL_PRODUCTION_CLAIMS.md", "docs/REAL_PRODUCTION_CLAIMS.md", "When real production quality can be claimed."),
    ("docs/COMIC_DOWNSTREAM_HANDOFF.md", "docs/COMIC_DOWNSTREAM_HANDOFF.md", "How the comic production package hands off downstream."),
    ("docs/NEW_OFFICE_STARTER_CHECKLIST.md", "docs/NEW_OFFICE_STARTER_CHECKLIST.md", "Checklist for adding future offices safely."),
]

VERIFY_COMMANDS = [
    ("first_run", [sys.executable, "scripts/verify_first_run_readiness.py", "--format", "json"]),
    ("model_guidance", [sys.executable, "scripts/verify_model_configuration_guidance.py", "--format", "json"]),
    ("public_docs", [sys.executable, "scripts/verify_public_docs_readability.py", "--format", "json"]),
    ("secret_scan", [sys.executable, "scripts/check_no_secrets.py"]),
]

FORBIDDEN_PATH_PARTS = {
    ".env",
    "config.yaml",
    "cookies.json",
    "user_data",
    "output",
    "runtime_logs",
    "logs",
    "browser_profiles",
    ".venv",
    ".vercel",
    "data/chroma",
}


def _relative(path: Path) -> str:
    return path.as_posix()


def _safe_copy(source_rel: str, target_rel: str, output_dir: Path) -> dict[str, Any]:
    target_path = Path(target_rel)
    lowered = {part.lower() for part in target_path.parts}
    if lowered & FORBIDDEN_PATH_PARTS:
        raise RuntimeError(f"Refusing to include forbidden path in onboarding packet: {target_rel}")
    source = REPO_ROOT / source_rel
    if not source.is_file():
        raise RuntimeError(f"Required onboarding source file is missing: {source_rel}")
    target = output_dir / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {
        "source": source_rel,
        "target": target_rel,
        "bytes": target.stat().st_size,
    }


def _run_command(name: str, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    parsed: Any = None
    if completed.stdout.strip().startswith("{"):
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "id": name,
        "command": " ".join(command).replace(str(sys.executable), "python"),
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "summary": _summarize_command(name, parsed, completed.stdout),
        "parsed_payload": parsed,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def _summarize_command(name: str, parsed: Any, stdout: str) -> str:
    if isinstance(parsed, dict):
        if name == "first_run":
            checklist = parsed.get("github_download_checklist") or {}
            return (
                f"status={parsed.get('status')}; "
                f"paths={','.join(parsed.get('recommended_order') or [])}; "
                f"github_download={checklist.get('status')}:{checklist.get('present_public_file_count')}/{checklist.get('expected_public_file_count')}"
            )
        if name == "model_guidance":
            return f"status={parsed.get('status')}; offices={parsed.get('office_count')}; checks={parsed.get('check_count')}"
        if name == "public_docs":
            return f"status={parsed.get('status')}; docs={parsed.get('passed_count')}/{parsed.get('doc_count')}; failures={len(parsed.get('failures') or [])}"
    if "Sensitive data scan passed" in stdout:
        return "tracked secrets and local runtime artifacts not found"
    return "see stdout_tail"


def _write_readme(output_dir: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Three Cobblers GitHub Onboarding Packet",
        "",
        "This local packet is for people who clone the repository and want to know what can be verified without any API key.",
        "",
        "Open order:",
        "",
        "1. `START_HERE.md`",
        "2. `README.md`",
        "3. `docs/FIRST_RUN_DECISION_CARD.md`",
        "4. `docs/MODEL_CONFIGURATION.md`",
        "5. `verification/first_run.json`",
        "6. `verification/model_guidance.json`",
        "7. `verification/public_docs.json`",
        "8. `verification/secret_scan.txt`",
        "",
        "Safe boundary:",
        "",
        "- This packet does not include `config.yaml`, API keys, cookies, browser profiles, `user_data`, `output`, logs, or real generated workspaces.",
        "- Public demo checks do not call real model providers.",
        "- Real production quality still requires the user's own local model configuration and post-run claim checks.",
        "",
        f"Generated at: `{manifest['generated_at']}`",
        f"Files copied: `{len(manifest['files'])}`",
        f"Verification checks: `{len(manifest['verification'])}`",
        "",
    ]
    (output_dir / "OPEN_THIS_FIRST.md").write_text("\n".join(lines), encoding="utf-8")


def _zip_directory(output_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(output_dir).as_posix()
                lowered = {part.lower() for part in Path(rel).parts}
                if lowered & FORBIDDEN_PATH_PARTS:
                    raise RuntimeError(f"Refusing to archive forbidden path: {rel}")
                archive.write(path, rel)


def export_packet(output_dir: Path = DEFAULT_OUTPUT, zip_path: Path = DEFAULT_ZIP) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "verification").mkdir(parents=True, exist_ok=True)

    copied = []
    for source, target, description in COPY_FILES:
        record = _safe_copy(source, target, output_dir)
        copied.append({**record, "description": description})

    verification = []
    errors = []
    for name, command in VERIFY_COMMANDS:
        result = _run_command(name, command)
        parsed_payload = result.pop("parsed_payload", None)
        verification.append(result)
        if parsed_payload is not None:
            (output_dir / "verification" / f"{name}.json").write_text(
                json.dumps(parsed_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            (output_dir / "verification" / f"{name}.txt").write_text(result["stdout_tail"], encoding="utf-8")
        if result["status"] != "passed":
            errors.append(f"{name} failed")

    manifest = {
        "mode": "github_onboarding_packet",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "archive_path": str(zip_path),
        "safe_for_public_review": True,
        "requires_api_key": False,
        "calls_real_models": False,
        "writes_workspace": False,
        "files": copied,
        "verification": verification,
        "forbidden_materials": sorted(FORBIDDEN_PATH_PARTS),
        "errors": errors,
        "status": "passed" if not errors else "failed",
    }
    _write_readme(output_dir, manifest)
    (output_dir / "packet-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _zip_directory(output_dir, zip_path)
    manifest["archive_bytes"] = zip_path.stat().st_size
    (output_dir / "packet-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# GitHub Onboarding Packet",
        "",
        f"Status: `{payload.get('status')}`",
        f"Output: `{payload.get('output_dir')}`",
        f"Archive: `{payload.get('archive_path')}`",
        f"Archive bytes: `{payload.get('archive_bytes')}`",
        f"Requires API key: `{payload.get('requires_api_key')}`",
        f"Calls real models: `{payload.get('calls_real_models')}`",
        f"Writes workspace: `{payload.get('writes_workspace')}`",
        "",
        "## Verification",
        "",
    ]
    for item in payload.get("verification") or []:
        lines.append(f"- `{item.get('id')}`: `{item.get('status')}` - {item.get('summary')}")
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--zip", default=str(DEFAULT_ZIP))
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()

    payload = export_packet(Path(args.output), Path(args.zip))
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
