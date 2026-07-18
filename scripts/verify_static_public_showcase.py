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
    "portfolio-deploy-manifest.json",
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


def verify_static_public_showcase(existing_dir: Path | str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    build_root = REPO_ROOT / "dist"
    build_root.mkdir(parents=True, exist_ok=True)
    should_cleanup = existing_dir is None
    if existing_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix=".verify-public-showcase-", dir=build_root))
    else:
        temp_dir = Path(existing_dir)
        if not temp_dir.is_absolute():
            temp_dir = REPO_ROOT / temp_dir
        temp_dir = temp_dir.resolve()
    try:
        if existing_dir is None:
            export_summary = export_public_showcase(temp_dir)
        else:
            export_summary = {
                "status": "existing_export",
                "output_dir": str(temp_dir),
                "requires_backend": False,
                "requires_api_key": False,
                "calls_real_models": False,
            }
            if not temp_dir.is_dir():
                return {
                    "status": "failed",
                    "mode": "public_no_key_static_showcase_readiness",
                    "summary": f"Existing static showcase directory is missing: {temp_dir}",
                    "verification_source": "existing_dir",
                    "errors": [f"missing existing directory: {temp_dir}"],
                }
        manifest = json.loads((temp_dir / "export-manifest.json").read_text(encoding="utf-8"))
        deploy_manifest = json.loads((temp_dir / "portfolio-deploy-manifest.json").read_text(encoding="utf-8"))
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
        if deploy_manifest.get("mode") != "public_no_key_portfolio_deploy":
            errors.append("portfolio deploy manifest has an unexpected mode")
        if deploy_manifest.get("source_dir") != "dist/public-showcase":
            errors.append("portfolio deploy manifest must preserve the static source directory")
        if deploy_manifest.get("personal_site_target") != "public/three-stooges/":
            errors.append("portfolio deploy manifest must expose the personal website copy target")
        if deploy_manifest.get("personal_site_url_path") != "/three-stooges/":
            errors.append("portfolio deploy manifest must expose the personal website URL path")
        for flag in ("requires_backend", "requires_api_key", "calls_real_models", "allows_workspace_writes"):
            if deploy_manifest.get(flag) is not False:
                errors.append(f"portfolio deploy manifest must keep {flag}=False")
        required_deploy_files = {
            "index.html",
            "data.js",
            "app.js",
            "style.css",
            "showcase.json",
            "export-manifest.json",
            "assets/public-showcase-desktop.png",
            "data/comic_production_claim_report.json",
            "downloads/",
        }
        if required_deploy_files - set(deploy_manifest.get("required_files") or []):
            errors.append("portfolio deploy manifest is missing required files")
        if deploy_manifest.get("sample_download_count") != len(manifest.get("downloads") or []):
            errors.append("portfolio deploy manifest download count does not match export downloads")
        if not any("verify_static_public_showcase.py" in item for item in deploy_manifest.get("verification_commands") or []):
            errors.append("portfolio deploy manifest must include the static showcase verifier")
        forbidden_manifest_text = json.dumps(deploy_manifest.get("forbidden_public_assets") or [], ensure_ascii=False)
        for marker in ("config.yaml", "API Key", "Cookie", "user_data/", "output/"):
            if marker not in forbidden_manifest_text:
                errors.append(f"portfolio deploy manifest must forbid {marker}")
        if len(deploy_manifest.get("operator_checklist") or []) < 4:
            errors.append("portfolio deploy manifest must include an operator checklist")
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
            if path.suffix == "":
                errors.append(f"static download must have a reviewer-friendly file extension: {local_uri}")
            if path.stat().st_size <= 20:
                errors.append(f"static download is too small: {local_uri}")
            if item.get("sha256") != _sha256(path):
                errors.append(f"static download hash mismatch: {local_uri}")

        download_catalog = showcase.get("download_catalog") or []
        if len(download_catalog) < 5:
            errors.append("static showcase must expose a top-level download_catalog with at least five reviewable files")
        if (showcase.get("static_export") or {}).get("reviewable_file_count") != len(download_catalog):
            errors.append("static showcase reviewable_file_count must match download_catalog")
        catalog_uris = {str(item.get("local_uri") or "") for item in download_catalog}
        if "data/comic_production_claim_report.json" not in catalog_uris:
            errors.append("download_catalog must include the real production claim report")
        for item in download_catalog:
            local_uri = str(item.get("local_uri") or "")
            path = temp_dir / local_uri
            if not local_uri or local_uri.startswith("/") or not path.is_file():
                errors.append(f"download_catalog item is not local: {local_uri}")
                continue
            if path.suffix == "":
                errors.append(f"download_catalog item must have a reviewer-friendly file extension: {local_uri}")
            if not item.get("title") or not item.get("sha256") or item.get("sha256") != _sha256(path):
                errors.append(f"download_catalog item is missing title or valid hash: {local_uri}")
            if int(item.get("bytes") or 0) != path.stat().st_size:
                errors.append(f"download_catalog item byte count mismatch: {local_uri}")
            if not (item.get("proves") or item.get("reader_guidance") or item.get("look_for")):
                errors.append(f"download_catalog item lacks visitor guidance: {local_uri}")

        portfolio = showcase.get("portfolio_embed") or {}
        release_badge = portfolio.get("release_badge") or {}
        real_production_claim = portfolio.get("real_production_claim") or {}
        research_claim_boundary = portfolio.get("research_claim_boundary") or {}
        quality_upgrade_path = portfolio.get("quality_upgrade_path") or {}
        office_extension_story = portfolio.get("office_extension_story") or {}
        portfolio_integration = portfolio.get("portfolio_integration") or {}
        claim_uri = str(real_production_claim.get("uri") or "")
        claim_path = temp_dir / claim_uri
        claim_payload = {}
        claim_upgrade_checklist = []
        claim_upgrade_recovery = {}
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
            claim_upgrade_recovery = claim_payload.get("claim_upgrade_recovery") or {}
            if claim_upgrade_recovery.get("recovery_action") != "regenerate_images":
                errors.append("static claim report must include regenerate_images recovery action")
            if claim_upgrade_recovery.get("required") is not True:
                errors.append("static claim report must mark recovery as required")
            if len(claim_upgrade_recovery.get("steps") or []) < 3:
                errors.append("static claim report must include recovery steps")
        research_claim_uri = str(research_claim_boundary.get("uri") or "")
        research_claim_path = temp_dir / research_claim_uri
        research_claim_payload = {}
        if research_claim_uri != "downloads/research/claim-report.json" or not research_claim_path.is_file():
            errors.append("static showcase must expose a local research office claim report")
        else:
            research_claim_payload = json.loads(research_claim_path.read_text(encoding="utf-8"))
            if research_claim_payload.get("claim_level") != "staged_research_demo":
                errors.append("static research claim report must remain staged_research_demo")
            if research_claim_payload.get("can_claim_full_automation") is not False:
                errors.append("static research claim report must not claim full automation")
            if research_claim_payload.get("calls_real_models") is not False:
                errors.append("static research claim report must not call real models")
            if research_claim_payload.get("requires_api_key") is not False:
                errors.append("static research claim report must not require an API Key")
            if "E:\\" in json.dumps(research_claim_payload, ensure_ascii=False):
                errors.append("static research claim report leaks a local Windows path")
            if len(research_claim_payload.get("claim_upgrade_checklist") or []) < 3:
                errors.append("static research claim report must include a claim upgrade checklist")
            if len(research_claim_payload.get("evidence_handoff") or []) < 3:
                errors.append("static research claim report must include evidence handoff items")
        if research_claim_boundary.get("claim_level") != "staged_research_demo":
            errors.append("static portfolio embed must expose the research staged claim level")
        if research_claim_boundary.get("can_claim_full_automation") is not False:
            errors.append("static portfolio embed must not claim research full automation")
        if research_claim_boundary.get("requires_api_key") is not False or research_claim_boundary.get("calls_real_models") is not False:
            errors.append("static portfolio embed must keep the research claim no-key and no-model")
        research_claim_upgrade_checklist = research_claim_payload.get("claim_upgrade_checklist") or []

        reading_guide = portfolio.get("deliverable_reading_guide") or []
        ready_reading_items = 0
        for item in reading_guide:
            uri = str(item.get("uri") or "")
            if uri and not uri.startswith("/") and (temp_dir / uri).is_file() and item.get("look_for") and item.get("proves"):
                ready_reading_items += 1
            else:
                errors.append(f"static reading guide item is not locally usable: {item.get('title') or uri}")

        first_run_paths = portfolio.get("first_run_paths") or []
        first_run_ids = {item.get("id") for item in first_run_paths}
        if first_run_ids != {"public_demo", "local_real_use", "developer_extension"}:
            errors.append("static showcase must expose the three first-run paths")
        for item in first_run_paths:
            if not item.get("title") or not item.get("for_user") or not item.get("start_here"):
                errors.append(f"static first-run path is missing user guidance: {item.get('id')}")
            if len(item.get("do_first") or []) < 3:
                errors.append(f"static first-run path must include at least three first actions: {item.get('id')}")
            if not item.get("verification") or not item.get("success_signal"):
                errors.append(f"static first-run path is missing verification guidance: {item.get('id')}")
        first_run_text = json.dumps(first_run_paths, ensure_ascii=False)
        for marker in ("verify_public_demo_mode.py", "doctor.py", "verify_office_extension_governance.py"):
            if marker not in first_run_text:
                errors.append(f"static first-run paths are missing marker: {marker}")

        reproducibility = portfolio.get("reproducibility_checklist") or []
        if len(reproducibility) < 5:
            errors.append("static showcase must include a 5-step reproducibility checklist")
        for item in reproducibility:
            if not item.get("command") or not item.get("expected") or not item.get("if_fails"):
                errors.append(f"static reproducibility item is incomplete: {item.get('title')}")
        if not any("verify_release_readiness.py" in str(item.get("command") or "") for item in reproducibility):
            errors.append("static reproducibility checklist must include the release readiness gate")
        post_run_validation = portfolio.get("post_run_validation") or []
        if [item.get("order") for item in post_run_validation] != [1, 2, 3]:
            errors.append("static showcase must include a 3-step real output validation checklist")
        ready_post_run_steps = 0
        post_run_text = json.dumps(post_run_validation, ensure_ascii=False)
        for marker in (
            "audit_comic_v2_handoffs.py",
            "verify_comic_real_production_claim.py",
            "verify_comic_v2_production_benchmark.py",
            "can_claim_real_quality=True",
            "production_quality_verified",
        ):
            if marker not in post_run_text:
                errors.append(f"static post-run validation is missing marker: {marker}")
        for item in post_run_validation:
            if item.get("command") and item.get("expected") and item.get("if_fails"):
                ready_post_run_steps += 1
            else:
                errors.append(f"static post-run validation item is incomplete: {item.get('title')}")
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
        shot_contract = portfolio.get("shot_contract") or {}
        shot_contract_text = json.dumps(shot_contract, ensure_ascii=False)
        for marker in ("first_frame_reference_image", "reference_asset_chain", "director_execution"):
            if marker not in shot_contract_text:
                errors.append(f"static shot contract is missing marker: {marker}")
        if shot_contract.get("manifest_uri") != "downloads/comic-production/files/handoff_manifest.json":
            errors.append("static shot contract must point to the local handoff manifest download")
        if "verify_comic_v2_downstream_handoff.py" not in str(shot_contract.get("release_gate") or ""):
            errors.append("static shot contract must link to the downstream handoff verifier")
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
        if quality_upgrade_path.get("current_public_level") != "demo_structure_only":
            errors.append("static quality upgrade path must start from demo_structure_only")
        if quality_upgrade_path.get("current_image_evidence") != "fixture_only":
            errors.append("static quality upgrade path must expose fixture_only public image evidence")
        if quality_upgrade_path.get("recovery_action") != "regenerate_images":
            errors.append("static quality upgrade path must point to regenerate_images")
        if quality_upgrade_path.get("trace_endpoint") != "/api/tasks/{task_id}/comic-v2-trace.json":
            errors.append("static quality upgrade path must expose the history trace endpoint")
        if len(quality_upgrade_path.get("steps") or []) < 3:
            errors.append("static quality upgrade path must include at least three operator steps")
        if portfolio_integration.get("recommended_path") != "static_export":
            errors.append("static portfolio integration must recommend static_export")
        integration_static = portfolio_integration.get("static_export") or {}
        if integration_static.get("source_dir") != "dist/public-showcase":
            errors.append("static portfolio integration must preserve dist/public-showcase source dir")
        if integration_static.get("requires_backend") is not False or integration_static.get("requires_api_key") is not False:
            errors.append("static portfolio integration must remain backend-free and no-key")
        integration_options = portfolio_integration.get("integration_options") or []
        if {"standalone_static_site", "personal_site_subdirectory"} - {item.get("id") for item in integration_options}:
            errors.append("static portfolio integration must document both integration options")
        if "public/three-stooges/" not in json.dumps(integration_options, ensure_ascii=False):
            errors.append("static portfolio integration must include personal website copy target")
        forbidden = "\n".join(portfolio_integration.get("must_not_include") or [])
        for marker in ("config.yaml", "API Key", "Cookie", "user_data/", "output/"):
            if marker not in forbidden:
                errors.append(f"static portfolio integration must forbid {marker}")
        extension_checklist = office_extension_story.get("starter_checklist") or []
        future_candidates = office_extension_story.get("future_office_candidates") or []
        future_backlog = office_extension_story.get("future_platform_backlog") or []
        if office_extension_story.get("starter_checklist_doc") != "docs/NEW_OFFICE_STARTER_CHECKLIST.md":
            errors.append("static showcase must expose the new office starter checklist document")
        if len(extension_checklist) != 8:
            errors.append("static showcase must expose the 8-step office extension checklist")
        extension_phases = {item.get("phase") for item in extension_checklist}
        for phase in ("product", "safety", "isolation", "workflow", "demo", "quality", "public_demo", "release"):
            if phase not in extension_phases:
                errors.append(f"static office extension story is missing phase: {phase}")
        extension_commands = "\n".join(office_extension_story.get("required_verifiers") or [])
        for marker in ("verify_office_isolation.py", "verify_office_extension_governance.py", "verify_release_readiness.py", "check_no_secrets.py"):
            if marker not in extension_commands:
                errors.append(f"static office extension story must include verifier command: {marker}")
        candidate_ids = {item.get("id") for item in future_candidates}
        for candidate_id in ("short_video_ads", "ecommerce_selection", "story_ip", "technical_project"):
            if candidate_id not in candidate_ids:
                errors.append(f"static showcase is missing future office candidate: {candidate_id}")
        for item in future_candidates:
            if not item.get("user_job") or not item.get("not_ready_reason") or not item.get("required_before_public"):
                errors.append(f"static showcase future office candidate is incomplete: {item.get('id')}")
        backlog_ids = {item.get("id") for item in future_backlog}
        for backlog_id in ("future_schema_validators", "future_recovery_events"):
            if backlog_id not in backlog_ids:
                errors.append(f"static showcase is missing future platform backlog: {backlog_id}")
        for item in future_backlog:
            if not item.get("description") or not item.get("evidence_required"):
                errors.append(f"static showcase future platform backlog item is incomplete: {item.get('id')}")

        demos = showcase.get("featured_demos") or []
        comic_prompt_quality: dict[str, Any] = {}
        for demo in demos:
            if demo.get("demo_uri") != f"#office-{demo.get('office_id')}":
                errors.append(f"featured demo does not use a local anchor: {demo.get('office_id')}")
            if demo.get("office_id") == "comic_production":
                prompt_quality = ((demo.get("quality_benchmark") or {}).get("prompt_quality_summary") or {})
                comic_prompt_quality = prompt_quality
                if prompt_quality.get("status") != "ready":
                    errors.append("static comic demo must expose ready prompt quality")
                if prompt_quality.get("asset_prompt_count") != prompt_quality.get("clean_asset_prompt_count"):
                    errors.append("static comic demo must expose all asset prompts as clean")
                if prompt_quality.get("shot_prompt_count") != prompt_quality.get("director_prompt_count"):
                    errors.append("static comic demo must expose all director prompts as ready")
                if prompt_quality.get("issue_count") != 0:
                    errors.append("static comic demo must expose zero prompt quality issues")

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
        app_text = (temp_dir / "app.js").read_text(encoding="utf-8")
        style_text = (temp_dir / "style.css").read_text(encoding="utf-8")
        if "claim.claim_upgrade_checklist" not in app_text or "claim-upgrade-card" not in app_text:
            errors.append("static showcase page must render the claim upgrade checklist")
        if "claim.claim_upgrade_recovery" not in app_text or "claim-recovery-card" not in app_text:
            errors.append("static showcase page must render the claim recovery playbook")
        if "portfolio.research_claim_boundary" not in app_text or "research-claim-card" not in app_text:
            errors.append("static showcase page must render the research claim boundary")
        if "showcase.download_catalog" not in app_text or "renderDownloadCatalog" not in app_text:
            errors.append("static showcase page must render the reviewable download catalog")
        if "portfolio.post_run_validation" not in app_text or "renderPostRunValidation" not in app_text:
            errors.append("static showcase page must render the real output validation checklist")
        if "portfolio.first_run_paths" not in app_text or "renderFirstRunPaths" not in app_text:
            errors.append("static showcase page must render the first-run paths")
        if "portfolio.shot_contract" not in app_text or "renderShotContract" not in app_text:
            errors.append("static showcase page must render the shot contract")
        if "portfolio.office_extension_story" not in app_text or "renderOfficeExtensionStory" not in app_text:
            errors.append("static showcase page must render the office extension story")
        if "future_office_candidates" not in app_text or "future_platform_backlog" not in app_text:
            errors.append("static showcase page must render future office candidates and platform backlog")
        if "claim-upgrade-item" not in style_text:
            errors.append("static showcase stylesheet must style the claim upgrade checklist")
        if "extension-check-grid" not in style_text or "extension-panel" not in style_text:
            errors.append("static showcase stylesheet must style the office extension checklist")
        if "first-run-grid" not in style_text or "first-run-card" not in style_text:
            errors.append("static showcase stylesheet must style the first-run paths")
        if "catalog-card" not in style_text or "hash-code" not in style_text:
            errors.append("static showcase stylesheet must style the reviewable download catalog")
        for marker in ("data.js", "app.js", "assets/public-showcase-desktop.png", "公开发布状态", "交付物阅读顺序", "可复核文件目录", "下游生产 quick-start", "复现与验收清单", "真实产物验收", "公开部署安全边界"):
            if marker not in index_text and marker not in (temp_dir / "style.css").read_text(encoding="utf-8"):
                errors.append(f"static showcase page is missing marker: {marker}")

        return {
            "status": "passed" if not errors else "failed",
            "mode": "public_no_key_static_showcase_readiness",
            "verification_source": "fresh_export" if existing_dir is None else "existing_dir",
            "summary": (
                "Static showcase is self-contained, backend-free, downloadable, and safe for public hosting."
                if not errors
                else "Static showcase readiness found gaps."
            ),
            "file_count": len(files),
            "download_count": len(downloads),
            "download_catalog_count": len(download_catalog),
            "reading_guide_count": len(reading_guide),
            "reading_guide_ready_count": ready_reading_items,
            "first_run_path_count": len(first_run_paths),
            "downstream_quick_start_count": len(downstream_quick_start),
            "downstream_quick_start_ready_count": ready_downstream_steps,
            "shot_contract_field_count": len(shot_contract.get("required_fields") or []),
            "reproducibility_count": len(reproducibility),
            "post_run_validation_count": len(post_run_validation),
            "post_run_validation_ready_count": ready_post_run_steps,
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
            "claim_upgrade_recovery_action": claim_upgrade_recovery.get("recovery_action", ""),
            "claim_upgrade_recovery_step_count": len(claim_upgrade_recovery.get("steps") or []),
            "research_claim_report_ready": bool(
                research_claim_payload.get("claim_level") == "staged_research_demo"
                and research_claim_payload.get("can_claim_full_automation") is False
            ),
            "research_claim_report_uri": research_claim_uri,
            "research_claim_level": research_claim_payload.get("claim_level", ""),
            "research_can_claim_full_automation": research_claim_payload.get("can_claim_full_automation"),
            "research_claim_upgrade_checklist_count": len(research_claim_upgrade_checklist),
            "research_evidence_handoff_count": len(research_claim_payload.get("evidence_handoff") or []),
            "quality_upgrade_recovery_action": quality_upgrade_path.get("recovery_action", ""),
            "quality_upgrade_step_count": len(quality_upgrade_path.get("steps") or []),
            "office_extension_checklist_count": len(extension_checklist),
            "office_extension_phase_count": len(extension_phases),
            "office_extension_doc": office_extension_story.get("starter_checklist_doc", ""),
            "office_extension_candidate_count": len(future_candidates),
            "office_extension_backlog_count": len(future_backlog),
            "comic_prompt_quality_status": comic_prompt_quality.get("status", ""),
            "comic_prompt_asset_clean_count": comic_prompt_quality.get("clean_asset_prompt_count", 0),
            "comic_prompt_asset_count": comic_prompt_quality.get("asset_prompt_count", 0),
            "comic_prompt_director_ready_count": comic_prompt_quality.get("director_prompt_count", 0),
            "comic_prompt_shot_count": comic_prompt_quality.get("shot_prompt_count", 0),
            "comic_prompt_issue_count": comic_prompt_quality.get("issue_count", 0),
            "portfolio_integration_option_count": len(integration_options),
            "portfolio_integration_source_dir": integration_static.get("source_dir", ""),
            "portfolio_deploy_manifest": "portfolio-deploy-manifest.json",
            "portfolio_deploy_target": deploy_manifest.get("personal_site_target", ""),
            "requires_backend": bool(manifest.get("requires_backend")),
            "requires_api_key": bool(manifest.get("requires_api_key")),
            "calls_real_models": bool(manifest.get("calls_real_models")),
            "export_summary": export_summary,
            "errors": errors,
        }
    finally:
        if should_cleanup and temp_dir.exists():
            shutil.rmtree(temp_dir)


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Static Public Showcase Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Verification source: `{payload.get('verification_source', 'fresh_export')}`",
        f"Summary: {payload.get('summary')}",
        "",
        f"- Files: {payload.get('file_count')}",
        f"- Downloadable deliverables: {payload.get('download_count')}",
        f"- Reviewable catalog: {payload.get('download_catalog_count')} files",
        f"- Reading guide: {payload.get('reading_guide_ready_count')}/{payload.get('reading_guide_count')}",
        f"- First-run paths: {payload.get('first_run_path_count')}",
        f"- Downstream quick-start: {payload.get('downstream_quick_start_ready_count')} steps",
        f"- Shot contract: {payload.get('shot_contract_field_count')} fields",
        f"- Reproducibility checklist: {payload.get('reproducibility_count')} commands",
        f"- Real output validation: {payload.get('post_run_validation_ready_count')}/{payload.get('post_run_validation_count')} steps",
        f"- Release badge: {payload.get('release_badge_status')} / signals={payload.get('release_badge_signal_count')}",
        f"- Featured demos: {payload.get('featured_demo_count')}",
        f"- Real product screenshot: {payload.get('screenshot_ready')}",
        f"- Comic claim report: {payload.get('claim_report_uri')} / ready={payload.get('claim_report_ready')}",
        f"- Claim upgrade checklist: {payload.get('claim_upgrade_checklist_count')} items",
        f"- Claim upgrade recovery: action={payload.get('claim_upgrade_recovery_action')} / steps={payload.get('claim_upgrade_recovery_step_count')}",
        f"- Research claim report: {payload.get('research_claim_report_uri')} / ready={payload.get('research_claim_report_ready')} / level={payload.get('research_claim_level')} / full_automation={payload.get('research_can_claim_full_automation')}",
        f"- Research claim upgrade checklist: {payload.get('research_claim_upgrade_checklist_count')} items / evidence_handoff={payload.get('research_evidence_handoff_count')}",
        f"- Quality upgrade path: action={payload.get('quality_upgrade_recovery_action')} / steps={payload.get('quality_upgrade_step_count')}",
        f"- New office extension: checklist={payload.get('office_extension_checklist_count')} / phases={payload.get('office_extension_phase_count')} / doc={payload.get('office_extension_doc')}",
        f"- Future office candidates: {payload.get('office_extension_candidate_count')} / backlog={payload.get('office_extension_backlog_count')}",
        f"- Prompt quality: {payload.get('comic_prompt_quality_status')} / assets={payload.get('comic_prompt_asset_clean_count')}/{payload.get('comic_prompt_asset_count')} / directors={payload.get('comic_prompt_director_ready_count')}/{payload.get('comic_prompt_shot_count')} / issues={payload.get('comic_prompt_issue_count')}",
        f"- Portfolio integration: source={payload.get('portfolio_integration_source_dir')} / options={payload.get('portfolio_integration_option_count')}",
        f"- Portfolio deploy manifest: {payload.get('portfolio_deploy_manifest')} / target={payload.get('portfolio_deploy_target')}",
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
    parser.add_argument(
        "--existing-dir",
        default=None,
        help="Verify an already exported static showcase directory, for example dist/public-showcase.",
    )
    args = parser.parse_args()
    payload = verify_static_public_showcase(args.existing_dir)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
