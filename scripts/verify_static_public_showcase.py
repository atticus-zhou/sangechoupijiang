"""Build and verify the self-contained static public showcase."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_no_secrets import SECRET_PATTERNS
from scripts.export_public_showcase import export_public_showcase


REQUIRED_FILES = {
    "index.html",
    "style.css",
    "app.js",
    "data.js",
    "showcase.json",
    "export-manifest.json",
    "assets/public-showcase-desktop.png",
    "data/comic_production.json",
    "data/comic_production_claim_report.json",
    "data/research.json",
}

FORBIDDEN_NAMES = {
    ".env",
    "config.yaml",
    "config.yml",
    "cookies.json",
    "user_data",
    "browser_profiles",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_text_files(root: Path) -> list[str]:
    findings: list[str] = []
    text_suffixes = {".html", ".css", ".js", ".json", ".md", ".txt"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                findings.append(path.relative_to(root).as_posix())
                break
    return findings


def verify_static_public_showcase() -> dict[str, Any]:
    errors: list[str] = []
    build_root = REPO_ROOT / "dist"
    build_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".verify-public-showcase-", dir=build_root))
    try:
        export_summary = export_public_showcase(temp_dir)
        manifest = json.loads((temp_dir / "export-manifest.json").read_text(encoding="utf-8"))
        showcase = json.loads((temp_dir / "showcase.json").read_text(encoding="utf-8"))
        files = {path.relative_to(temp_dir).as_posix() for path in temp_dir.rglob("*") if path.is_file()}

        missing_files = sorted(REQUIRED_FILES - files)
        if missing_files:
            errors.append("static showcase missing files: " + ", ".join(missing_files))

        if manifest.get("requires_backend") is not False:
            errors.append("static showcase must not require a backend")
        if manifest.get("requires_api_key") is not False:
            errors.append("static showcase must not require an API Key")
        if manifest.get("calls_real_models") is not False:
            errors.append("static showcase must not call real models")
        if showcase.get("mode") != "public_no_key_static_showcase":
            errors.append("static showcase has an unexpected mode")
        if (showcase.get("static_export") or {}).get("requires_backend") is not False:
            errors.append("showcase manifest does not declare the backend-free boundary")

        downloads = manifest.get("downloads") or []
        if len(downloads) < 4:
            errors.append("static showcase must contain at least four downloadable deliverables")
        for item in downloads:
            local_uri = str(item.get("local_uri") or "")
            path = temp_dir / local_uri
            if not local_uri or local_uri.startswith("/") or not path.is_file():
                errors.append(f"static download is missing or non-local: {local_uri}")
                continue
            if path.stat().st_size <= 20:
                errors.append(f"static download is too small: {local_uri}")
            if item.get("sha256") != _sha256(path):
                errors.append(f"static download hash mismatch: {local_uri}")

        portfolio = showcase.get("portfolio_embed") or {}
        release_badge = portfolio.get("release_badge") or {}
        real_production_claim = portfolio.get("real_production_claim") or {}
        claim_uri = str(real_production_claim.get("uri") or "")
        claim_path = temp_dir / claim_uri
        claim_payload = {}
        if claim_uri != "data/comic_production_claim_report.json" or not claim_path.is_file():
            errors.append("static showcase must expose a local comic production claim report")
        else:
            claim_payload = json.loads(claim_path.read_text(encoding="utf-8"))
            if claim_payload.get("claim_level") != "demo_structure_only":
                errors.append("static claim report must remain demo_structure_only")
            if claim_payload.get("can_claim_real_quality") is not False:
                errors.append("static claim report must not claim real production quality")
            if claim_payload.get("calls_real_models") is not False:
                errors.append("static claim report must not call real models")
            if claim_payload.get("requires_api_key") is not False:
                errors.append("static claim report must not require an API Key")
            if "E:\\" in json.dumps(claim_payload, ensure_ascii=False):
                errors.append("static claim report leaks a local Windows path")
            claim_upgrade_checklist = claim_payload.get("claim_upgrade_checklist") or []
            if len(claim_upgrade_checklist) < 3:
                errors.append("static claim report must include a claim upgrade checklist")
            for item in claim_upgrade_checklist:
                if not item.get("id") or not item.get("status") or not item.get("required_evidence") or not item.get("why_it_matters"):
                    errors.append(f"static claim upgrade checklist item is incomplete: {item.get('id') or item.get('title')}")
        if not claim_payload:
            claim_upgrade_checklist = []

        reading_guide = portfolio.get("deliverable_reading_guide") or []
        ready_reading_items = 0
        for item in reading_guide:
            uri = str(item.get("uri") or "")
            if uri and not uri.startswith("/") and (temp_dir / uri).is_file() and item.get("look_for") and item.get("proves"):
                ready_reading_items += 1
            else:
                errors.append(f"static reading guide item is not locally usable: {item.get('title') or uri}")

        reproducibility = portfolio.get("reproducibility_checklist") or []
        if len(reproducibility) < 5:
            errors.append("static showcase must include a 5-step reproducibility checklist")
        for item in reproducibility:
            if not item.get("command") or not item.get("expected") or not item.get("if_fails"):
                errors.append(f"static reproducibility item is incomplete: {item.get('title')}")
        if not any("verify_release_readiness.py" in str(item.get("command") or "") for item in reproducibility):
            errors.append("static reproducibility checklist must include the release readiness gate")
        downstream_quick_start = portfolio.get("downstream_quick_start") or []
        if [item.get("step") for item in downstream_quick_start] != [1, 2, 3, 4, 5]:
            errors.append("static showcase must include a 5-step downstream quick-start")
        ready_downstream_steps = 0
        for item in downstream_quick_start:
            if (
                item.get("owner")
                and len(item.get("input_refs") or []) >= 2
                and item.get("action")
                and item.get("output")
                and item.get("acceptance")
            ):
                ready_downstream_steps += 1
            else:
                errors.append(f"static downstream quick-start item is incomplete: {item.get('title') or item.get('step')}")
        if release_badge.get("status") != "safe_public_demo":
            errors.append("static showcase must include a safe_public_demo release badge")
        if release_badge.get("mode") != "demo_only":
            errors.append("static release badge must stay demo_only")
        if release_badge.get("can_claim_real_quality") is not False:
            errors.append("static release badge must not claim real visual quality")
        if "verify_release_readiness.py" not in str(release_badge.get("primary_gate") or ""):
            errors.append("static release badge must link to release readiness")
        if len(release_badge.get("signals") or []) < 5:
            errors.append("static release badge must include at least five signals")

        demos = showcase.get("featured_demos") or []
        for demo in demos:
            if demo.get("demo_uri") != f"#office-{demo.get('office_id')}":
                errors.append(f"featured demo does not use a local anchor: {demo.get('office_id')}")

        screenshot = temp_dir / "assets" / "public-showcase-desktop.png"
        screenshot_ready = screenshot.is_file() and screenshot.stat().st_size > 100_000
        if not screenshot_ready:
            errors.append("static showcase is missing the real product screenshot")

        forbidden_paths = []
        for path in temp_dir.rglob("*"):
            relative_parts = {part.lower() for part in path.relative_to(temp_dir).parts}
            if relative_parts & FORBIDDEN_NAMES:
                forbidden_paths.append(path.relative_to(temp_dir).as_posix())
        if forbidden_paths:
            errors.append("static showcase contains forbidden local paths: " + ", ".join(sorted(forbidden_paths)))

        secret_like_files = _scan_text_files(temp_dir)
        if secret_like_files:
            errors.append("static showcase contains secret-like values: " + ", ".join(secret_like_files))

        index_text = (temp_dir / "index.html").read_text(encoding="utf-8")
        for marker in ("data.js", "app.js", "assets/public-showcase-desktop.png", "公开发布状态", "交付物阅读顺序", "下游生产 quick-start", "复现与验收清单", "公开部署安全边界"):
            if marker not in index_text and marker not in (temp_dir / "style.css").read_text(encoding="utf-8"):
                errors.append(f"static showcase page is missing marker: {marker}")

        return {
            "status": "passed" if not errors else "failed",
            "mode": "public_no_key_static_showcase_readiness",
            "summary": (
                "Static showcase is self-contained, backend-free, downloadable, and safe for public hosting."
                if not errors
                else "Static showcase readiness found gaps."
            ),
            "file_count": len(files),
            "download_count": len(downloads),
            "reading_guide_count": len(reading_guide),
            "reading_guide_ready_count": ready_reading_items,
            "downstream_quick_start_count": len(downstream_quick_start),
            "downstream_quick_start_ready_count": ready_downstream_steps,
            "reproducibility_count": len(reproducibility),
            "release_badge_status": release_badge.get("status", ""),
            "release_badge_signal_count": len(release_badge.get("signals") or []),
            "featured_demo_count": len(demos),
            "screenshot_ready": screenshot_ready,
            "claim_report_ready": bool(
                claim_payload.get("claim_level") == "demo_structure_only"
                and claim_payload.get("can_claim_real_quality") is False
            ),
            "claim_report_uri": claim_uri,
            "claim_upgrade_checklist_count": len(claim_upgrade_checklist),
            "requires_backend": bool(manifest.get("requires_backend")),
            "requires_api_key": bool(manifest.get("requires_api_key")),
            "calls_real_models": bool(manifest.get("calls_real_models")),
            "export_summary": export_summary,
            "errors": errors,
        }
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Static Public Showcase Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Summary: {payload.get('summary')}",
        "",
        f"- Files: {payload.get('file_count')}",
        f"- Downloadable deliverables: {payload.get('download_count')}",
        f"- Reading guide: {payload.get('reading_guide_ready_count')}/{payload.get('reading_guide_count')}",
        f"- Downstream quick-start: {payload.get('downstream_quick_start_ready_count')} steps",
        f"- Reproducibility checklist: {payload.get('reproducibility_count')} commands",
        f"- Release badge: {payload.get('release_badge_status')} / signals={payload.get('release_badge_signal_count')}",
        f"- Featured demos: {payload.get('featured_demo_count')}",
        f"- Real product screenshot: {payload.get('screenshot_ready')}",
        f"- Comic claim report: {payload.get('claim_report_uri')} / ready={payload.get('claim_report_ready')}",
        f"- Claim upgrade checklist: {payload.get('claim_upgrade_checklist_count')} items",
        f"- Requires backend: {payload.get('requires_backend')}",
        f"- Requires API Key: {payload.get('requires_api_key')}",
        f"- Calls real models: {payload.get('calls_real_models')}",
    ]
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify the backend-free public showcase export.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()
    payload = verify_static_public_showcase()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
