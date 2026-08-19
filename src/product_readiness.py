"""Evidence-backed readiness checks for product-level office milestones."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from scripts.audit_comic_v2_handoffs import audit_handoff_inventory
from src.llm.providers import ModelConfig
from src.office_preflight import build_office_preflight


REPO_ROOT = Path(__file__).resolve().parents[1]


def audit_comic_real_production_start_readiness(
    get_model_config: Callable[[str, str], ModelConfig],
    *,
    base_dir: Path | str | None = None,
) -> dict:
    """Return the current no-key, no-call readiness to attempt a real comic production run."""
    root = Path(base_dir) if base_dir is not None else REPO_ROOT
    preflight = build_office_preflight("comic_production", get_model_config, base_dir=root)
    inventory = audit_handoff_inventory([root / "output"])
    capabilities = preflight.get("capabilities") or []
    by_id = {item.get("id"): item for item in capabilities}
    required_for_full_package = (
        "story_planning",
        "asset_planning",
        "prompt_planning",
        "image_generation",
        "visual_review",
        "local_output",
    )
    missing_full = [
        item
        for item in (by_id.get(check_id) for check_id in required_for_full_package)
        if item and item.get("status") != "ok"
    ]
    blockers = [item for item in missing_full if item.get("status") == "blocked"]
    missing_optional = [item for item in missing_full if item.get("status") != "blocked"]
    if blockers:
        status = "blocked"
        can_start_full = False
        can_start_limited = False
        summary = "核心文本规划或本地输出能力未就绪，不建议开始真实漫剧生产。"
        next_action = blockers[0].get("next_action") or preflight.get("next_action") or ""
    elif missing_optional:
        status = "limited_planning_only"
        can_start_full = False
        can_start_limited = True
        summary = "可以先做故事、资产拆解和提示词规划，但还不能生成完整带图片与自动质检的制片包。"
        next_action = missing_optional[0].get("next_action") or preflight.get("next_action") or ""
    else:
        status = "ready_for_real_run"
        can_start_full = True
        can_start_limited = True
        summary = "当前模型配置和本地输出目录具备完整真实制片包生产条件。"
        next_action = "可以开始真实生产；完成后运行交付盘点和质量基准，确认是否达到 production_quality_verified。"
    return {
        "office_id": "comic_production",
        "mode": "real_production_start_readiness",
        "status": status,
        "summary": summary,
        "can_start_full_production": can_start_full,
        "can_start_limited_planning": can_start_limited,
        "calls_real_models": False,
        "requires_api_key_to_check": False,
        "writes_workspace": False,
        "next_action": next_action,
        "preflight_status": preflight.get("status", ""),
        "preflight_summary": preflight.get("summary", ""),
        "blocking_reasons": preflight.get("blocking_reasons", []),
        "required_capabilities": [
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "status": item.get("status", ""),
                "owner_label": item.get("owner_label", ""),
                "model_kind": item.get("model_kind", ""),
                "impact": item.get("impact", ""),
                "next_action": item.get("next_action", ""),
            }
            for item in capabilities
            if item.get("id") in required_for_full_package
        ],
        "handoff_inventory": {
            "manifest_count": inventory.get("manifest_count", 0),
            "production_verified_count": inventory.get("production_verified_count", 0),
            "demo_only_count": inventory.get("demo_only_count", 0),
            "needs_review_count": inventory.get("needs_review_count", 0),
            "legacy_unverifiable_count": inventory.get("legacy_unverifiable_count", 0),
            "safe_public_claim": inventory.get("safe_public_claim", ""),
            "next_action": inventory.get("next_action", ""),
        },
        "operator_checklist": [
            "先在模型页测试中书省、门下省、工部、兵部、刑部的配置。",
            "确认工部是生图模型，刑部是视觉理解模型，文本部门不是误填成纯生图模型。",
            "开始真实生产前确认 output 目录可写，且公开部署没有暴露个人密钥。",
            "真实生产完成后运行 python scripts/audit_comic_v2_handoffs.py --format markdown。",
            "只有交付盘点和质量基准显示 production_quality_verified 时，才把该包说成真实质量已验证。",
        ],
        "post_run_validation": [
            {
                "step": 1,
                "title": "盘点本地制片包",
                "command": "python scripts/audit_comic_v2_handoffs.py --format markdown",
                "passes_when": "最近一份真实项目显示 production_quality_verified，或明确列出 needs_review 的责任部门和恢复动作。",
                "if_fails": "先按表格里的 Recovery/Stage 修复；不要把 needs_review 或 legacy_unverifiable 当成可交付成品。",
            },
            {
                "step": 2,
                "title": "审计目标 manifest 的真实生产声明",
                "command": "python scripts/verify_comic_real_production_claim.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown",
                "passes_when": "Claim level 为 real_quality_verified，且 Can claim real quality 为 True。",
                "if_fails": "把报告里的 Claim Upgrade Checklist 当成补证据清单；不要公开宣称真实画质已验证。",
            },
            {
                "step": 3,
                "title": "复核制片包质量基准",
                "command": "python scripts/verify_comic_v2_production_benchmark.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown",
                "passes_when": "package_quality_ready、production_quality_verified 和 stored_benchmark_matches 都成立。",
                "if_fails": "按 recommended_recovery 退回图片、提示词、质检或交付组装阶段。",
            },
            {
                "step": 4,
                "title": "保留交付证据",
                "command": "下载或归档 Word 画布、handoff manifest、提示词包、图片记录和追溯 JSON。",
                "passes_when": "历史页和 manifest 能互相指向同一批故事、资产、图片、镜头和质量基准版本。",
                "if_fails": "先重新生成交付包或追溯记录；不要只保留一个 Word 文件。",
            },
        ],
    }


def audit_comic_real_production_start_readiness(
    get_model_config: Callable[[str, str], ModelConfig],
    *,
    base_dir: Path | str | None = None,
) -> dict:
    """Return no-key readiness to start, plus whether any real output is verified."""
    root = Path(base_dir) if base_dir is not None else REPO_ROOT
    preflight = build_office_preflight("comic_production", get_model_config, base_dir=root)
    inventory = audit_handoff_inventory([root / "output"])
    capabilities = preflight.get("capabilities") or []
    by_id = {item.get("id"): item for item in capabilities}
    required_for_full_package = (
        "story_planning",
        "asset_planning",
        "prompt_planning",
        "image_generation",
        "visual_review",
        "local_output",
    )
    missing_full = [
        item
        for item in (by_id.get(check_id) for check_id in required_for_full_package)
        if item and item.get("status") != "ok"
    ]
    blockers = [item for item in missing_full if item.get("status") == "blocked"]
    missing_optional = [item for item in missing_full if item.get("status") != "blocked"]
    if blockers:
        status = "blocked"
        can_start_full = False
        can_start_limited = False
        summary = "核心文本规划或本地输出能力还没有就绪，不建议开始真实漫剧生产。"
        next_action = blockers[0].get("next_action") or preflight.get("next_action") or ""
    elif missing_optional:
        status = "limited_planning_only"
        can_start_full = False
        can_start_limited = True
        summary = "可以先做故事、资产拆解和提示词规划，但还不能生成完整带图片与自动质检的制片包。"
        next_action = missing_optional[0].get("next_action") or preflight.get("next_action") or ""
    else:
        status = "ready_for_real_run"
        can_start_full = True
        can_start_limited = True
        summary = "当前模型配置和本地输出目录具备完整真实制片包的启动条件。"
        next_action = "可以开始真实生产；完成后必须运行交付盘点和质量基准，确认是否达到 production_quality_verified。"

    production_verified_count = int(inventory.get("production_verified_count", 0) or 0)
    has_verified_output = production_verified_count > 0
    verified_output_status = "real_quality_verified" if has_verified_output else "structure_demo_only"
    verified_output_summary = (
        f"已发现 {production_verified_count} 份真实质量通过的制片包，可以作为真实产物证据。"
        if has_verified_output
        else "当前只证明本机具备开跑条件，还没有发现真实质量通过的制片包；公开展示只能说有结构样例和本地生产能力。"
    )
    verified_output_next_action = (
        "选择最近一份 production_quality_verified 产物进入公开样例或作品集说明。"
        if has_verified_output
        else "跑完一次真实任务后，先用 handoff audit、real claim 和 production benchmark 验证，再决定能否公开宣称真实画质。"
    )

    return {
        "office_id": "comic_production",
        "mode": "real_production_start_readiness",
        "status": status,
        "start_readiness_status": status,
        "summary": summary,
        "can_start_full_production": can_start_full,
        "can_start_limited_planning": can_start_limited,
        "has_verified_real_output": has_verified_output,
        "verified_output_status": verified_output_status,
        "verified_output_summary": verified_output_summary,
        "verified_output_next_action": verified_output_next_action,
        "calls_real_models": False,
        "requires_api_key_to_check": False,
        "writes_workspace": False,
        "next_action": next_action,
        "preflight_status": preflight.get("status", ""),
        "preflight_summary": preflight.get("summary", ""),
        "blocking_reasons": preflight.get("blocking_reasons", []),
        "required_capabilities": [
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "status": item.get("status", ""),
                "owner_label": item.get("owner_label", ""),
                "model_kind": item.get("model_kind", ""),
                "impact": item.get("impact", ""),
                "next_action": item.get("next_action", ""),
            }
            for item in capabilities
            if item.get("id") in required_for_full_package
        ],
        "handoff_inventory": {
            "manifest_count": inventory.get("manifest_count", 0),
            "production_verified_count": production_verified_count,
            "demo_only_count": inventory.get("demo_only_count", 0),
            "needs_review_count": inventory.get("needs_review_count", 0),
            "legacy_unverifiable_count": inventory.get("legacy_unverifiable_count", 0),
            "safe_public_claim": inventory.get("safe_public_claim", ""),
            "next_action": inventory.get("next_action", ""),
        },
        "operator_checklist": [
            "先在模型页面测试中书省、门下省、尚书省、户部、礼部、兵部、工部、刑部的配置。",
            "确认工部是生图模型，刑部是视觉理解模型，文本部门没有误填成纯生图模型。",
            "开始真实生产前确认 output 目录可写，且公开部署没有暴露个人密钥。",
            "真实生产完成后运行 python scripts/audit_comic_v2_handoffs.py --format markdown。",
            "只有交付盘点和质量基准显示 production_quality_verified 时，才能把该包说成真实质量已验证。",
        ],
        "post_run_validation": [
            {
                "step": 1,
                "title": "盘点本地制片包",
                "command": "python scripts/audit_comic_v2_handoffs.py --format markdown",
                "passes_when": "最近一份真实项目显示 production_quality_verified，或明确列出 needs_review 的责任部门和恢复动作。",
                "if_fails": "先按表格里的 Recovery/Stage 修复；不要把 needs_review 或 legacy_unverifiable 当成可交付成品。",
            },
            {
                "step": 2,
                "title": "审计目标 manifest 的真实生产声明",
                "command": "python scripts/verify_comic_real_production_claim.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown",
                "passes_when": "Claim level 为 real_quality_verified，且 Can claim real quality 为 True。",
                "if_fails": "把报告里的 Claim Upgrade Checklist 当成补证据清单；不要公开宣称真实画质已验证。",
            },
            {
                "step": 3,
                "title": "复核制片包质量基准",
                "command": "python scripts/verify_comic_v2_production_benchmark.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown",
                "passes_when": "package_quality_ready、production_quality_verified 和 stored_benchmark_matches 都成立。",
                "if_fails": "按 recommended_recovery 退回图片、提示词、质检或交付组装阶段。",
            },
            {
                "step": 4,
                "title": "保留交付证据",
                "command": "下载或归档 Word 画布、handoff manifest、提示词包、图片记录和追溯 JSON。",
                "passes_when": "历史页和 manifest 能互相指向同一批故事、资产、图片、镜头和质量基准版本。",
                "if_fails": "先重新生成交付包或追溯记录；不要只保留一个 Word 文件。",
            },
        ],
    }


def audit_comic_production_readiness(base_dir: Path | str | None = None) -> dict:
    """Audit product readiness for the AI comic production office."""
    root = Path(base_dir) if base_dir is not None else REPO_ROOT
    checks = [
        _check(
            "workflow_state",
            "完整工作流状态",
            [
                _contains(root / "src/comic_office/v2/pipeline.py", "ready_for_handoff"),
                _contains(root / "src/web/static/js/app.js", "production_chain_state"),
                _contains(root / "tests/test_frontend_comic_routing.py", "department_flow"),
            ],
            [
                "src/comic_office/v2/pipeline.py",
                "src/web/static/js/app.js",
                "tests/test_frontend_comic_routing.py",
            ],
        ),
        _check(
            "downloadable_delivery",
            "可下载交付物",
            [
                _contains(root / "src/web/app.py", "/files/delivery/"),
                _contains(root / "tests/test_web_comic_api.py", "word_canvas_uri"),
                _exists(root / "scripts/verify_comic_v2_delivery.py"),
            ],
            [
                "src/web/app.py",
                "tests/test_web_comic_api.py",
                "scripts/verify_comic_v2_delivery.py",
            ],
        ),
        _check(
            "model_preflight",
            "模型预检",
            [
                _contains(root / "src/office_preflight.py", "story_planning"),
                _contains(root / "src/office_preflight.py", "image_generation"),
                _contains(root / "src/office_preflight.py", "visual_review"),
                _contains(root / "tests/test_system_preflight.py", "preflight"),
            ],
            [
                "src/office_preflight.py",
                "tests/test_system_preflight.py",
            ],
        ),
        _check(
            "real_production_start_check",
            "真实生产前检查",
            [
                _contains(root / "src/product_readiness.py", "audit_comic_real_production_start_readiness"),
                _contains(root / "src/product_readiness.py", "ready_for_real_run"),
                _contains(root / "src/product_readiness.py", "limited_planning_only"),
                _contains(root / "src/web/app.py", "/api/offices/{office_id}/real-production-readiness"),
                _contains(root / "src/web/static/js/app.js", "renderRealProductionReadiness"),
                _contains(root / "src/web/static/js/app.js", "/api/offices/${officeId}/real-production-readiness"),
                _contains(root / "tests/test_office_preflight.py", "test_comic_real_production_readiness_reports_full_ready_without_calling_models"),
                _contains(root / "tests/test_frontend_comic_routing.py", "renderRealProductionReadiness"),
                _contains(root / "README.md", "/api/offices/comic_production/real-production-readiness"),
            ],
            [
                "src/product_readiness.py:audit_comic_real_production_start_readiness",
                "src/web/app.py:/api/offices/{office_id}/real-production-readiness",
                "src/web/static/js/app.js:renderRealProductionReadiness",
                "tests/test_office_preflight.py",
                "tests/test_frontend_comic_routing.py",
                "README.md",
            ],
        ),
        _check(
            "local_doctor",
            "本地自检命令",
            [
                _contains(root / "scripts/doctor.py", "三个臭皮匠本地自检"),
                _contains(root / "scripts/doctor.py", "办公室可用性"),
                _contains(root / "scripts/doctor.py", '"offices"'),
                _contains(root / "scripts/doctor.py", "build_system_preflight"),
                _contains(root / "scripts/doctor.py", "build_office_preflight"),
                _contains(root / "README.md", "python scripts/doctor.py"),
                _contains(root / "tests/test_doctor_script.py", "DoctorScriptTests"),
            ],
            [
                "scripts/doctor.py",
                "scripts/doctor.py:办公室可用性",
                'scripts/doctor.py:"offices"',
                "README.md",
                "tests/test_doctor_script.py",
            ],
        ),
        _check(
            "end_to_end_verifier",
            "端到端测试",
            [
                _exists(root / "scripts/verify_comic_v2_user_flow.py"),
                _contains(root / "tests/test_comic_v2_user_flow_verifier.py", "ready_for_handoff"),
                _contains(root / "tests/test_comic_v2_user_flow_verifier.py", "download_bytes"),
            ],
            [
                "scripts/verify_comic_v2_user_flow.py",
                "tests/test_comic_v2_user_flow_verifier.py",
            ],
        ),
        _check(
            "first_run_reproducibility",
            "First-run reproducibility",
            [
                _contains(root / "scripts/verify_first_run_readiness.py", "public_demo"),
                _contains(root / "scripts/verify_first_run_readiness.py", "local_real_use"),
                _contains(root / "scripts/verify_first_run_readiness.py", "developer_extension"),
                _contains(root / "scripts/verify_first_run_readiness.py", "python run.py --port 8080"),
                _contains(root / "tests/test_first_run_readiness_verifier.py", "FirstRunReadinessVerifierTests"),
                _contains(root / "README.md", "python scripts/verify_first_run_readiness.py --format markdown"),
            ],
            [
                "scripts/verify_first_run_readiness.py",
                "tests/test_first_run_readiness_verifier.py",
                "README.md",
            ],
        ),
        _check(
            "history_trace",
            "历史追溯",
            [
                _contains(root / "src/web/app.py", '"shots": handoff_meta.get("shots")'),
                _contains(root / "src/web/static/js/app.js", "renderComicV2HistoryShotPackages(trace.shots)"),
                _contains(root / "tests/test_web_comic_api.py", "trace[\"shots\"]"),
                _contains(root / "tests/test_frontend_comic_routing.py", "镜头生产包"),
            ],
            [
                "src/web/app.py",
                "src/web/static/js/app.js",
                "tests/test_web_comic_api.py",
                "tests/test_frontend_comic_routing.py",
            ],
        ),
        _check(
            "no_key_demo",
            "无 Key 演示",
            [
                _contains(root / "src/web/app.py", "/api/demo/comic-production"),
                _contains(root / "src/web/app.py", "/api/demo/research"),
                _contains(root / "src/web/app.py", "/api/demo/public-showcase"),
                _contains(root / "src/web/static/index.html", 'id="product-showcase"'),
                _contains(root / "src/web/static/index.html", 'id="btn-open-research-demo"'),
                _contains(root / "src/web/app.py", "quality_gates"),
                _contains(root / "src/web/static/js/app.js", "loadComicDemo"),
                _contains(root / "src/web/static/js/app.js", "loadResearchDemo"),
                _contains(root / "src/web/static/js/app.js", "renderDemoQualityGates"),
                _contains(root / "src/offices.py", "evidence_links"),
                _contains(root / "src/offices.py", "/api/demo/comic-production/files/word_canvas.docx"),
                _contains(root / "src/offices.py", "/api/demo/research/files/report.md"),
                _contains(root / "src/web/static/css/style.css", "demo-quality-gates"),
                _contains(root / "scripts/verify_public_demo_mode.py", "verify_public_demo_mode"),
                _contains(root / "tests/test_public_demo_verifier.py", "PublicDemoVerifierTests"),
                _contains(root / "tests/test_office_preflight.py", "test_comic_production_demo_api_is_no_key_and_read_only"),
                _contains(root / "tests/test_office_preflight.py", "test_research_demo_api_is_no_key_and_read_only"),
            ],
            [
                "src/web/app.py:/api/demo/comic-production",
                "src/web/app.py:/api/demo/research",
                "src/web/app.py:/api/demo/public-showcase",
                "src/web/app.py:quality_gates",
                "src/web/static/index.html",
                "src/web/static/js/app.js",
                "src/web/static/js/app.js:renderDemoQualityGates",
                "src/offices.py:evidence_links",
                "src/offices.py:/api/demo/comic-production/files/word_canvas.docx",
                "src/offices.py:/api/demo/research/files/report.md",
                "src/web/static/css/style.css",
                "src/web/static/css/style.css:demo-quality-gates",
                "scripts/verify_public_demo_mode.py",
                "tests/test_public_demo_verifier.py",
                "tests/test_office_preflight.py",
            ],
        ),
        _check(
            "office_protocols",
            "办公室协议",
            [
                _contains(root / "src/offices.py", "input_types"),
                _contains(root / "src/offices.py", "output_types"),
                _contains(root / "src/offices.py", "model_requirements"),
                _contains(root / "src/offices.py", "human_checkpoints"),
                _contains(root / "src/offices.py", "artifact_contract"),
                _contains(root / "src/web/app.py", "/api/offices/protocols"),
                _contains(root / "tests/test_office_preflight.py", "test_office_protocol_api_declares_platform_contracts"),
            ],
            [
                "src/offices.py",
                "src/web/app.py:/api/offices/protocols",
                "tests/test_office_preflight.py",
            ],
        ),
        _check(
            "office_isolation_contract",
            "Office isolation contract",
            [
                _contains(root / "src/config_manager.py", 'payload.get("workspace_id")'),
                _contains(root / "src/config_manager.py", "exact_task_id_set"),
                _contains(root / "src/config_manager.py", "office_models"),
                _contains(root / "scripts/verify_office_isolation.py", "model_config_isolation"),
                _contains(root / "scripts/verify_office_isolation.py", "history_trace_isolation"),
                _contains(root / "scripts/verify_office_isolation.py", "filesystem_output_isolation"),
                _contains(root / "tests/test_office_isolation_verifier.py", "test_json_proves_models_workspaces_artifacts_and_history_are_office_scoped"),
            ],
            [
                "src/config_manager.py:list_workspace_task_runs",
                "scripts/verify_office_isolation.py",
                "tests/test_office_isolation_verifier.py",
            ],
        ),
        _check(
            "office_launch_gate_audit",
            "Office launch gate audit",
            [
                _contains(root / "src/offices.py", "def audit_office_launch_gates"),
                _contains(root / "src/web/app.py", "/api/offices/{office_id}/launch-gates"),
                _contains(root / "src/web/static/index.html", 'id="office-launch-gates-panel"'),
                _contains(root / "src/web/static/js/app.js", "loadOfficeLaunchGates"),
                _contains(root / "src/web/static/js/app.js", "gate.evidence_links"),
                _contains(root / "src/web/static/js/app.js", "launch-gate-links"),
                _contains(root / "src/web/static/css/style.css", ".launch-gates-panel"),
                _contains(root / "src/web/static/css/style.css", ".launch-gate-links"),
                _contains(root / "tests/test_office_preflight.py", "test_office_launch_gate_api_returns_productization_audit"),
                _contains(root / "tests/test_frontend_comic_routing.py", "test_office_hall_renders_launch_gate_audit"),
                _contains(root / "README.md", "/api/offices/{office_id}/launch-gates"),
            ],
            [
                "src/offices.py:audit_office_launch_gates",
                "src/web/app.py:/api/offices/{office_id}/launch-gates",
                "src/web/static/index.html:office-launch-gates-panel",
                "src/web/static/js/app.js:loadOfficeLaunchGates",
                "src/web/static/js/app.js:evidence_links",
                "src/web/static/js/app.js:launch-gate-links",
                "src/web/static/css/style.css:.launch-gates-panel",
                "src/web/static/css/style.css:.launch-gate-links",
                "tests/test_office_preflight.py",
                "tests/test_frontend_comic_routing.py",
                "README.md",
            ],
        ),
        _check(
            "office_extension_governance",
            "Office extension governance",
            [
                _contains(root / "src/offices.py", "def audit_office_extension_governance"),
                _contains(root / "src/offices.py", "PRIMARY_OFFICE_IDS"),
                _contains(root / "src/offices.py", "PRIMARY_OFFICE_STANDARDS"),
                _contains(root / "scripts/verify_office_extension_governance.py", "Office Extension Governance Audit"),
                _contains(root / "tests/test_office_extension_governance_verifier.py", "test_json_proves_primary_office_can_be_promoted"),
                _contains(root / "README.md", "verify_office_extension_governance.py"),
            ],
            [
                "src/offices.py:audit_office_extension_governance",
                "scripts/verify_office_extension_governance.py",
                "tests/test_office_extension_governance_verifier.py",
                "README.md",
            ],
        ),
        _check(
            "research_office_readiness",
            "Research office readiness",
            [
                _contains(root / "scripts/verify_research_office_readiness.py", "Research Office Readiness Audit"),
                _contains(root / "scripts/verify_research_office_readiness.py", "assess_research_package"),
                _contains(root / "scripts/verify_research_office_readiness.py", "/api/demo/research/files/report.md"),
                _contains(root / "tests/test_research_office_readiness_verifier.py", "test_json_verifies_traceable_research_package_and_demo_downloads"),
                _contains(root / "src/research_artifacts.py", "screenshot_plan"),
                _contains(root / "src/research_quality.py", "REQUIRED_ARTIFACTS"),
            ],
            [
                "scripts/verify_research_office_readiness.py",
                "tests/test_research_office_readiness_verifier.py",
                "src/research_artifacts.py",
                "src/research_quality.py",
            ],
        ),
        _check(
            "artifact_contract_runtime",
            "产物协议运行时校验",
            [
                _contains(root / "src/config_manager.py", "def _normalize_artifact_metadata"),
                _contains(root / "src/config_manager.py", "artifact metadata missing required contract fields"),
                _contains(root / "src/config_manager.py", "reference_chain must be a list"),
                _contains(root / "tests/test_config_manager.py", "test_artifact_metadata_is_normalized_to_office_contract"),
                _contains(root / "tests/test_config_manager.py", "test_artifact_contract_rejects_missing_identity"),
            ],
            [
                "src/config_manager.py",
                "tests/test_config_manager.py",
            ],
        ),
        _check(
            "task_recovery_plan",
            "任务失败恢复计划",
            [
                _contains(root / "src/config_manager.py", "_build_task_recovery_plan"),
                _contains(root / "src/config_manager.py", "_office_retry_action"),
                _contains(root / "src/offices.py", "recovery_actions"),
                _contains(root / "src/offices.py", "delivery/build"),
                _contains(root / "src/offices.py", "recover-artifacts"),
                _contains(root / "src/config_manager.py", '"recovery_plan"'),
                _contains(root / "src/web/app.py", '"retry_action"'),
                _contains(root / "src/offices.py", "document_generation"),
                _contains(root / "src/offices.py", "agent_workflow"),
                _contains(root / "src/web/static/js/app.js", "renderTaskRecoveryPlan"),
                _contains(root / "src/web/static/css/style.css", ".task-recovery-plan"),
                _contains(root / "tests/test_config_manager.py", "test_failed_task_run_exposes_recovery_plan_from_last_failure_event"),
                _contains(root / "tests/test_config_manager.py", "test_comic_v2_recovery_plan_infers_retry_action_from_failed_stage"),
                _contains(root / "tests/test_config_manager.py", "test_research_recovery_plan_infers_retry_action_from_failed_stage"),
                _contains(root / "tests/test_offices.py", "recovery_actions"),
                _contains(root / "tests/test_office_preflight.py", "recovery_actions"),
                _contains(root / "tests/test_web_comic_api.py", "test_task_detail_exposes_recovery_plan_for_failed_run"),
                _contains(root / "tests/test_web_comic_api.py", "test_task_detail_exposes_delivery_retry_action_for_word_canvas_failure"),
                _contains(root / "tests/test_web_research_api.py", "test_research_background_failure_records_recoverable_task_event"),
                _contains(root / "tests/test_frontend_comic_routing.py", "test_task_timelines_render_recovery_plan"),
            ],
            [
                "src/config_manager.py",
                "src/offices.py",
                "src/web/app.py",
                "src/web/static/js/app.js",
                "src/web/static/css/style.css",
                "tests/test_config_manager.py",
                "tests/test_offices.py",
                "tests/test_office_preflight.py",
                "tests/test_web_comic_api.py",
                "tests/test_web_research_api.py",
                "tests/test_frontend_comic_routing.py",
            ],
        ),
        _check(
            "runtime_status",
            "办公室运行状态",
            [
                _contains(root / "src/office_runtime.py", "def build_office_runtime_status"),
                _contains(root / "src/office_runtime.py", "artifact_progress"),
                _contains(root / "src/office_runtime.py", "recovery_actions"),
                _contains(root / "src/web/app.py", "/api/workspaces/{workspace_id}/runtime-status"),
                _contains(root / "src/web/static/index.html", 'id="comic-runtime-status-panel"'),
                _contains(root / "src/web/static/js/app.js", "function renderOfficeRuntimeStatus"),
                _contains(root / "src/web/static/js/app.js", "loadComicRuntimeStatus(workspaceId)"),
                _contains(root / "src/web/static/css/style.css", ".runtime-status-panel"),
                _contains(root / "tests/test_office_runtime.py", "test_runtime_status_summarizes_workspace_artifacts_and_recovery"),
                _contains(root / "tests/test_office_runtime.py", "test_runtime_status_api_exposes_same_workspace_view"),
                _contains(root / "tests/test_frontend_comic_routing.py", "test_comic_workbench_renders_runtime_status_panel"),
            ],
            [
                "src/office_runtime.py",
                "src/web/app.py:/api/workspaces/{workspace_id}/runtime-status",
                "src/web/static/index.html",
                "src/web/static/js/app.js",
                "src/web/static/css/style.css",
                "tests/test_office_runtime.py",
                "tests/test_frontend_comic_routing.py",
            ],
        ),
        _check(
            "long_task_observability",
            "长任务可观测",
            [
                _contains(root / "src/web/app.py", 'event_type="task_started"'),
                _contains(root / "src/web/app.py", 'event_type="task_finished"'),
                _contains(root / "src/web/app.py", 'event_type="comic_v2_images_started"'),
                _contains(root / "src/web/app.py", 'event_type="comic_v2_delivery_started"'),
                _contains(root / "src/web/app.py", 'event_type="comic_v2_delivery_ready"'),
                _contains(root / "src/web/app.py", 'event_type="comic_image_item_started"'),
                _contains(root / "src/web/app.py", 'event_type="comic_image_item_completed"'),
                _contains(root / "src/web/app.py", 'event_type="comic_image_item_failed"'),
                _contains(root / "src/web/static/js/app.js", "timeline-events"),
                _contains(root / "src/web/static/js/app.js", "eventLabel"),
                _contains(root / "scripts/verify_comic_v2_user_flow.py", '"event_count"'),
                _contains(root / "tests/test_comic_v2_pipeline.py", "test_image_generation_writes_visible_start_and_result_events"),
                _contains(root / "tests/test_comic_v2_pipeline.py", "test_delivery_build_writes_visible_start_and_result_events"),
                _contains(root / "tests/test_comic_image_pipeline.py", "test_image_batch_records_per_image_progress_events"),
                _contains(root / "tests/test_frontend_comic_routing.py", "test_comic_image_progress_events_have_human_labels"),
            ],
            [
                "src/web/app.py",
                "src/web/static/js/app.js",
                "scripts/verify_comic_v2_user_flow.py",
                "tests/test_comic_v2_pipeline.py",
                "tests/test_comic_image_pipeline.py",
                "tests/test_frontend_comic_routing.py",
            ],
        ),
        _check(
            "agent_output_schema_gate",
            "Agent output schema gate",
            [
                _contains(root / "src/comic_office/v2/output_schemas.py", "comic_contract"),
                _contains(root / "src/comic_office/v2/output_schemas.py", "visual_revision"),
                _contains(root / "src/comic_office/v2/output_schemas.py", "asset_manifest"),
                _contains(root / "src/comic_office/v2/output_schemas.py", "asset_manifest_revision"),
                _contains(root / "src/comic_office/v2/output_schemas.py", "asset_prompt_set"),
                _contains(root / "src/comic_office/v2/output_schemas.py", "shot_cards"),
                _contains(root / "src/comic_office/v2/output_schemas.py", "image_review_result"),
                _contains(root / "src/offices.py", "schema_gates"),
                _contains(root / "src/offices.py", "comic_contract"),
                _contains(root / "src/offices.py", "image_review_result"),
                _contains(root / "src/offices.py", "research_standard_report"),
                _contains(root / "src/research_office/output_schemas.py", "research_standard_report"),
                _contains(root / "src/research_office/output_schemas.py", "research_source_list"),
                _contains(root / "src/research_office/output_schemas.py", "research_data_table"),
                _contains(root / "src/research_artifacts.py", "validate_research_output_schema"),
                _contains(root / "src/research_artifacts.py", "_apply_research_schema_gates"),
                _contains(root / "src/web/static/js/app.js", "renderArtifactSchemaGatePanel"),
                _contains(root / "src/web/static/css/style.css", "artifact-schema-gate"),
                _contains(root / "src/comic_office/v2/planner.py", "validate_agent_output_schema"),
                _contains(root / "src/comic_office/v2/asset_planner.py", "validate_agent_output_schema"),
                _contains(root / "src/comic_office/v2/production.py", "validate_agent_output_schema"),
                _contains(root / "tests/test_comic_v2_output_schemas.py", "test_schema_registry_exposes_comic_contract_gates"),
                _contains(root / "tests/test_comic_v2_asset_planner.py", "test_planner_output_must_pass_agent_schema_gate"),
                _contains(root / "tests/test_comic_v2_prompt_director.py", "test_direct_asset_prompts_must_pass_agent_schema_gate"),
                _contains(root / "tests/test_comic_v2_production.py", "test_generation_rejects_image_review_when_schema_gate_fails"),
                _contains(root / "tests/test_research_output_schemas.py", "test_research_schema_registry_declares_core_delivery_gates"),
                _contains(root / "tests/test_research_artifacts.py", "test_research_artifacts_record_schema_gate_audits"),
            ],
            [
                "src/comic_office/v2/output_schemas.py",
                "src/offices.py",
                "src/research_office/output_schemas.py",
                "src/research_artifacts.py",
                "src/web/static/js/app.js",
                "src/web/static/css/style.css",
                "src/comic_office/v2/planner.py",
                "src/comic_office/v2/asset_planner.py",
                "src/comic_office/v2/production.py",
                "tests/test_comic_v2_output_schemas.py",
                "tests/test_comic_v2_asset_planner.py",
                "tests/test_comic_v2_prompt_director.py",
                "tests/test_comic_v2_production.py",
                "tests/test_research_output_schemas.py",
                "tests/test_research_artifacts.py",
            ],
        ),
        _check(
            "readme",
            "清晰 README",
            [
                _contains(root / "README.md", "AI 漫剧制片办公室"),
                _contains(root / "README.md", "verify_comic_v2_user_flow.py"),
                _contains(root / "README.md", "office_models"),
                _contains(root / "README.md", "办公室协议"),
            ],
            ["README.md"],
        ),
        _check(
            "failure_handling",
            "失败处理策略",
            [
                _contains(root / "src/web/app.py", "def _comic_v2_http_error"),
                _contains(root / "src/web/app.py", '"department"'),
                _contains(root / "src/web/app.py", '"impact"'),
                _contains(root / "src/web/app.py", '"next_action"'),
                _contains(root / "tests/test_comic_v2_pipeline.py", "wrong_stage_error"),
            ],
            [
                "src/web/app.py",
                "tests/test_comic_v2_pipeline.py",
            ],
        ),
    ]
    failed = [item for item in checks if item["status"] != "passed"]
    return {
        "office_id": "comic_production",
        "mode": "real_product_with_no_key_demo",
        "status": "needs_work" if failed else "ready_with_demo",
        "summary": (
            "AI 漫剧制片办公室真实产品条件已具备，并提供不消耗模型密钥的固定样例演示入口。"
            if not failed else
            "AI 漫剧制片办公室仍有真实产品条件缺口。"
        ),
        "checks": checks,
    }


def format_readiness_markdown(audit: dict) -> str:
    rows = [
        "# AI 漫剧制片办公室真实产品 readiness",
        "",
        f"- 状态：{audit.get('status', '')}",
        f"- 模式：{audit.get('mode', '')}",
        f"- 说明：{audit.get('summary', '')}",
        "",
        "| 条件 | 状态 | 证据 |",
        "| --- | --- | --- |",
    ]
    for item in audit.get("checks", []):
        evidence = "<br>".join(item.get("evidence", []))
        rows.append(f"| {item.get('title', '')} | {item.get('status', '')} | {evidence} |")
    runtime = audit.get("runtime_verification") or {}
    if runtime:
        rows.extend([
            "",
            "## 运行时验证",
            "",
            "| 验证 | 状态 | 结果 |",
            "| --- | --- | --- |",
        ])
        stage_b = runtime.get("stage_b_product_loop") or {}
        if stage_b:
            passed = [
                f"{item.get('id')}={item.get('passed')}"
                for item in stage_b.get("requirements", [])
            ]
            rows.append(
                "| 阶段 B 产品闭环 | "
                f"{stage_b.get('status', '')} | "
                + "; ".join(passed)
                + " |"
            )
        delivery = runtime.get("delivery") or {}
        if delivery:
            rows.append(
                "| Word 交付链路 | "
                f"{delivery.get('status', '')} | "
                f"handoff_ready={delivery.get('handoff_ready', '')}; "
                f"assets={delivery.get('asset_count', 0)}; "
                f"shots={delivery.get('shot_count', 0)}; "
                f"embedded_images={delivery.get('embedded_images', 0)}; "
                f"handoff_manifest={delivery.get('handoff_manifest_exists', False)}; "
                f"image_prompts={delivery.get('handoff_manifest_image_prompts', False)}; "
                f"asset_identity={delivery.get('handoff_manifest_asset_identity_fields', False)}; "
                f"asset_baseline_chain={delivery.get('handoff_manifest_asset_baseline_chain', False)}; "
                f"shot_refs={delivery.get('handoff_manifest_shot_reference_images', False)}; "
                f"shot_notes={delivery.get('handoff_manifest_shot_execution_notes', False)}; "
                f"shot_package={delivery.get('handoff_manifest_shot_production_package', False)}; "
                f"lineage={delivery.get('handoff_manifest_production_lineage', False)}; "
                f"lineage_handoff={delivery.get('handoff_manifest_lineage_handoff_fields', False)}; "
                f"quick_start={delivery.get('handoff_manifest_downstream_quick_start_steps', 0)}; "
                f"word_asset_files={delivery.get('word_canvas_asset_file_references', False)}; "
                f"word_handoff={delivery.get('word_canvas_agent_handoff', False)} |"
            )
        user_flow = runtime.get("user_flow") or {}
        if user_flow:
            rows.append(
                "| 用户操作链路 | "
                f"{user_flow.get('status', '')} | "
                f"final_stage={user_flow.get('final_stage', '')}; "
                f"asset_baseline_chain={user_flow.get('handoff_manifest_asset_baseline_chain', False)}; "
                f"shot_package={user_flow.get('handoff_manifest_shot_production_package', False)}; "
                f"lineage_handoff={user_flow.get('production_lineage_handoff_fields', False)}; "
                f"generated_images={user_flow.get('generated_images', 0)}; "
                f"download_bytes={user_flow.get('download_bytes', 0)} |"
            )
    return "\n".join(rows)


def _check(check_id: str, title: str, assertions: list[bool], evidence: list[str]) -> dict:
    return {
        "id": check_id,
        "title": title,
        "status": "passed" if all(assertions) else "failed",
        "evidence": evidence if all(assertions) else [],
    }


def _exists(path: Path) -> bool:
    return path.exists()


def _contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return needle in path.read_text(encoding="utf-8", errors="ignore")
