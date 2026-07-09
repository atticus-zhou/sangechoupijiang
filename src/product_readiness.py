"""Evidence-backed readiness checks for product-level office milestones."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


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
            "AI 漫剧制片办公室真实产品条件已具备，并提供不消耗 API Key 的固定样例演示入口。"
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
