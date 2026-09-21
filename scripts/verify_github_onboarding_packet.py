"""Verify the no-key GitHub onboarding packet is complete and safe to publish."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from export_github_onboarding_packet import DEFAULT_OUTPUT, DEFAULT_ZIP, export_packet


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


REQUIRED_FILES = {
    "OPEN_THIS_FIRST.md",
    "START_HERE.md",
    "README.md",
    "config.example.yaml",
    "docs/FIRST_RUN_DECISION_CARD.md",
    "docs/MODEL_CONFIGURATION.md",
    "docs/MODEL_CAPABILITY_MATRIX.json",
    "docs/STATIC_SHOWCASE_DEPLOYMENT.md",
    "docs/PUBLIC_RELEASE_HANDOFF.md",
    "docs/PRODUCTIZATION_STATUS.md",
    "docs/REAL_PRODUCTION_CLAIMS.md",
    "docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md",
    "docs/COMIC_REAL_RUN_EVIDENCE_TEMPLATE.json",
    "docs/RESEARCH_EVIDENCE_INTAKE_TEMPLATE.json",
    "docs/OFFICE_EXPANSION_DECISION_BRIEF.md",
    "verification/first_run.json",
    "verification/productization_status.json",
    "verification/model_guidance.json",
    "verification/public_docs.json",
    "verification/secret_scan.txt",
    "packet-manifest.json",
}

REQUIRED_VERIFICATION_IDS = {
    "first_run",
    "productization_status",
    "model_guidance",
    "public_docs",
    "secret_scan",
}

FORBIDDEN_PARTS = {
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

REQUIRED_OPEN_FIRST_MARKERS = [
    "START_HERE.md",
    "docs/MODEL_CONFIGURATION.md",
    "docs/OFFICE_EXPANSION_DECISION_BRIEF.md",
    "docs/COMIC_REAL_RUN_EVIDENCE_TEMPLATE.json",
    "docs/RESEARCH_EVIDENCE_INTAKE_TEMPLATE.json",
    "--evidence-file",
    "--strict-real-values",
    "does not include `config.yaml`",
    "do not call real model providers",
]


def _error(message: str, *, item: str, path: str | None = None) -> dict[str, str]:
    payload = {"item": item, "message": message}
    if path:
        payload["path"] = path
    return payload


def _zip_names(zip_path: Path) -> set[str]:
    with zipfile.ZipFile(zip_path) as archive:
        return set(archive.namelist())


def verify_packet(output_dir: Path = DEFAULT_OUTPUT, zip_path: Path = DEFAULT_ZIP) -> dict[str, Any]:
    manifest = export_packet(output_dir=output_dir, zip_path=zip_path)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if manifest.get("status") != "passed":
        errors.append(_error("exporter returned a failing status", item="export_status"))
    for key in ("requires_api_key", "calls_real_models", "writes_workspace"):
        if manifest.get(key) is not False:
            errors.append(_error(f"manifest {key} must be false", item=key))
    if manifest.get("safe_for_public_review") is not True:
        errors.append(_error("packet must be explicitly marked safe for public review", item="safe_for_public_review"))

    if not zip_path.is_file():
        errors.append(_error("archive file was not created", item="archive", path=str(zip_path)))
        names: set[str] = set()
    else:
        if zip_path.stat().st_size <= 1000:
            errors.append(_error("archive is unexpectedly small", item="archive", path=str(zip_path)))
        names = _zip_names(zip_path)

    missing = sorted(REQUIRED_FILES - names)
    for name in missing:
        errors.append(_error("required onboarding file is missing from archive", item="archive_file", path=name))

    for name in sorted(names):
        lowered_parts = {part.lower() for part in Path(name).parts}
        forbidden = lowered_parts & FORBIDDEN_PARTS
        if forbidden:
            errors.append(_error(f"archive includes forbidden path part: {', '.join(sorted(forbidden))}", item="archive_forbidden_path", path=name))

    verification = {item.get("id"): item for item in manifest.get("verification") or []}
    missing_verification = sorted(REQUIRED_VERIFICATION_IDS - set(verification))
    for check_id in missing_verification:
        errors.append(_error("required verification check is missing", item="verification", path=check_id))
    for check_id, item in sorted(verification.items()):
        if item.get("status") != "passed":
            errors.append(_error("verification check did not pass", item="verification", path=str(check_id)))

    open_first = output_dir / "OPEN_THIS_FIRST.md"
    if not open_first.is_file():
        errors.append(_error("OPEN_THIS_FIRST.md was not created", item="open_first", path=str(open_first)))
    else:
        content = open_first.read_text(encoding="utf-8")
        for marker in REQUIRED_OPEN_FIRST_MARKERS:
            if marker not in content:
                errors.append(_error("OPEN_THIS_FIRST.md is missing required guidance", item="open_first_marker", path=marker))

    copied_targets = {item.get("target") for item in manifest.get("files") or []}
    for required in sorted(REQUIRED_FILES):
        if required.startswith("verification/") or required in {"OPEN_THIS_FIRST.md", "packet-manifest.json"}:
            continue
        if required not in copied_targets:
            warnings.append(_error("file is in the archive but not listed as a copied source", item="manifest_file_index", path=required))

    status = "passed" if not errors else "failed"
    return {
        "status": status,
        "output_dir": str(output_dir),
        "archive_path": str(zip_path),
        "archive_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        "required_files": len(REQUIRED_FILES),
        "archive_files": len(names),
        "verification_checks": sorted(verification),
        "errors": errors,
        "warnings": warnings,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# GitHub Onboarding Packet Verification",
        "",
        f"Status: `{payload['status']}`",
        f"Output: `{payload['output_dir']}`",
        f"Archive: `{payload['archive_path']}`",
        f"Archive bytes: `{payload['archive_bytes']}`",
        f"Required files: `{payload['required_files']}`",
        f"Archive files: `{payload['archive_files']}`",
        f"Verification checks: `{', '.join(payload['verification_checks'])}`",
    ]
    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item.get('item')}` `{item.get('path', '')}`: {item.get('message')}" for item in payload["warnings"])
    if payload["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item.get('item')}` `{item.get('path', '')}`: {item.get('message')}" for item in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--zip", default=str(DEFAULT_ZIP))
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()

    payload = verify_packet(Path(args.output), Path(args.zip))
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
