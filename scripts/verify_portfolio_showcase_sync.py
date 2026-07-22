"""Verify that the product static showcase matches the personal website copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "dist" / "public-showcase"
DEFAULT_PERSONAL_SITE = Path(os.environ.get("THREE_COBBLERS_PERSONAL_SITE", r"E:\trae\me\personal-website-v2"))
FORBIDDEN_TARGET_PARTS = {
    ".env",
    "config.yaml",
    "config.yml",
    "cookies.json",
    "browser_profiles",
    "user_data",
    "output",
    "runtime_logs",
}


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_file_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("path") or ""): item
        for item in manifest.get("files") or []
        if item.get("path")
    }


def verify_portfolio_showcase_sync(source_dir: Path | str = DEFAULT_SOURCE, target_dir: Path | str | None = None) -> dict[str, Any]:
    source = _resolve_repo_path(source_dir)
    if target_dir is None:
        target = (DEFAULT_PERSONAL_SITE / "public" / "three-stooges").resolve()
        target_source = "default_personal_site"
        target_required = False
    else:
        target = Path(target_dir)
        if not target.is_absolute():
            target = (REPO_ROOT / target).resolve()
        else:
            target = target.resolve()
        target_source = "explicit_target_dir"
        target_required = True

    errors: list[str] = []
    warnings: list[str] = []
    compared_files = 0
    mismatched_files: list[str] = []
    missing_files: list[str] = []
    extra_files: list[str] = []

    if not source.is_dir():
        errors.append(f"source showcase directory is missing: {source}")
        return {
            "status": "failed",
            "mode": "portfolio_showcase_sync",
            "source_dir": str(source),
            "target_dir": str(target),
            "target_source": target_source,
            "compared_files": 0,
            "source_file_count": 0,
            "target_actual_file_count": 0,
            "missing_files": missing_files,
            "mismatched_files": mismatched_files,
            "extra_files": extra_files,
            "warnings": warnings,
            "errors": errors,
        }
    if not target.is_dir():
        if target_required:
            errors.append(f"target showcase directory is missing: {target}")
        else:
            warnings.append(
                "default personal website target is not present; pass --target-dir after copying dist/public-showcase into a portfolio site"
            )
            return {
                "status": "skipped",
                "mode": "portfolio_showcase_sync",
                "source_dir": str(source),
                "target_dir": str(target),
                "target_source": target_source,
                "compared_files": 0,
                "source_file_count": 0,
                "target_actual_file_count": 0,
                "missing_files": missing_files,
                "mismatched_files": mismatched_files,
                "extra_files": extra_files,
                "warnings": warnings,
                "errors": errors,
                "next_action": "Copy dist/public-showcase into a portfolio directory such as public/three-stooges, then rerun with --target-dir.",
            }
    if errors:
        return {
            "status": "failed",
            "mode": "portfolio_showcase_sync",
            "source_dir": str(source),
            "target_dir": str(target),
            "target_source": target_source,
            "compared_files": 0,
            "missing_files": missing_files,
            "mismatched_files": mismatched_files,
            "extra_files": extra_files,
            "warnings": warnings,
            "errors": errors,
        }

    source_manifest_path = source / "export-manifest.json"
    target_manifest_path = target / "export-manifest.json"
    if not source_manifest_path.is_file():
        errors.append("source export-manifest.json is missing")
    if not target_manifest_path.is_file():
        errors.append("target export-manifest.json is missing")
    if errors:
        return {
            "status": "failed",
            "mode": "portfolio_showcase_sync",
            "source_dir": str(source),
            "target_dir": str(target),
            "target_source": target_source,
            "compared_files": 0,
            "missing_files": missing_files,
            "mismatched_files": mismatched_files,
            "extra_files": extra_files,
            "warnings": warnings,
            "errors": errors,
        }

    source_manifest = _read_json(source_manifest_path)
    target_manifest = _read_json(target_manifest_path)
    source_files = _manifest_file_map(source_manifest)
    target_manifest_files = _manifest_file_map(target_manifest)
    actual_target_files = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }

    if source_manifest.get("mode") != "public_no_key_static_export":
        errors.append("source export manifest mode must be public_no_key_static_export")
    if target_manifest.get("mode") != "public_no_key_static_export":
        errors.append("target export manifest mode must be public_no_key_static_export")
    for flag in ("requires_backend", "requires_api_key", "calls_real_models"):
        if source_manifest.get(flag) is not False:
            errors.append(f"source manifest must keep {flag}=False")
        if target_manifest.get(flag) is not False:
            errors.append(f"target manifest must keep {flag}=False")

    for relative, source_record in sorted(source_files.items()):
        target_file = target / relative
        if not target_file.is_file():
            missing_files.append(relative)
            continue
        compared_files += 1
        target_hash = _sha256(target_file)
        target_bytes = target_file.stat().st_size
        if source_record.get("sha256") != target_hash or int(source_record.get("bytes") or 0) != target_bytes:
            mismatched_files.append(relative)

    if target_manifest_path.is_file():
        compared_files += 1
        if _sha256(source_manifest_path) != _sha256(target_manifest_path):
            mismatched_files.append("export-manifest.json")

    expected_paths = set(source_files) | {"export-manifest.json"}
    extra_files = sorted(actual_target_files - expected_paths)
    target_manifest_missing = sorted(set(source_files) - set(target_manifest_files))
    if target_manifest_missing:
        errors.append("target export manifest is missing records: " + ", ".join(target_manifest_missing[:10]))
    for relative in extra_files:
        lowered_parts = {part.lower() for part in Path(relative).parts}
        if lowered_parts & FORBIDDEN_TARGET_PARTS:
            errors.append(f"target showcase contains forbidden public asset: {relative}")

    if missing_files:
        errors.append("target showcase is missing files copied from dist/public-showcase")
    if mismatched_files:
        errors.append("target showcase files differ from dist/public-showcase")
    if extra_files:
        warnings.append("target showcase has extra files not recorded in the source export manifest")

    deploy_manifest = target / "portfolio-deploy-manifest.json"
    showcase_json = target / "showcase.json"
    if deploy_manifest.is_file():
        deploy_payload = _read_json(deploy_manifest)
        live = deploy_payload.get("live_verification") or {}
        if live.get("check_command") != "npm run check:online":
            errors.append("target deploy manifest must keep npm run check:online as the live proof")
        if live.get("status") != "external_required":
            errors.append("target deploy manifest must keep live status external_required")
    if showcase_json.is_file():
        showcase = _read_json(showcase_json)
        live = (showcase.get("public_deployment") or {}).get("live_verification") or {}
        if live.get("check_command") != "npm run check:online":
            errors.append("target showcase must keep npm run check:online as the live proof")
        if live.get("status") != "external_required":
            errors.append("target showcase must keep live status external_required")

    return {
        "status": "passed" if not errors else "failed",
        "mode": "portfolio_showcase_sync",
        "source_dir": str(source),
        "target_dir": str(target),
        "target_source": target_source,
        "compared_files": compared_files,
        "source_file_count": len(expected_paths),
        "target_actual_file_count": len(actual_target_files),
        "missing_files": missing_files,
        "mismatched_files": mismatched_files,
        "extra_files": extra_files,
        "warnings": warnings,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Portfolio Showcase Sync",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Source: `{payload.get('source_dir')}`",
        f"Target: `{payload.get('target_dir')}`",
        f"Compared files: {payload.get('compared_files')}/{payload.get('source_file_count', 0)}",
        f"Target actual files: {payload.get('target_actual_file_count', 0)}",
        f"Missing files: {len(payload.get('missing_files') or [])}",
        f"Mismatched files: {len(payload.get('mismatched_files') or [])}",
        f"Extra files: {len(payload.get('extra_files') or [])}",
        "",
        "Meaning: this check proves the personal website copy has the same static files and hashes as `dist/public-showcase`; it does not prove the live Vercel domain has redeployed.",
    ]
    if payload.get("next_action"):
        lines.extend(["", f"Next action: {payload.get('next_action')}"])
    for title, key in (
        ("Missing Files", "missing_files"),
        ("Mismatched Files", "mismatched_files"),
        ("Extra Files", "extra_files"),
        ("Warnings", "warnings"),
        ("Errors", "errors"),
    ):
        values = payload.get(key) or []
        if values:
            lines.extend(["", f"## {title}", ""])
            lines.extend(f"- {item}" for item in values[:20])
            if len(values) > 20:
                lines.append(f"- ... {len(values) - 20} more")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify that the personal website static showcase copy matches dist/public-showcase.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE), help="Source static showcase directory.")
    parser.add_argument("--target-dir", default=None, help="Target showcase directory, for example E:/trae/me/personal-website-v2/public/three-stooges.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()
    payload = verify_portfolio_showcase_sync(args.source_dir, args.target_dir)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
