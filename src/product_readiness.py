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
                _contains(root / "src/web/static/index.html", 'id="product-showcase"'),
                _contains(root / "src/web/static/index.html", 'id="btn-open-research-demo"'),
                _contains(root / "src/web/static/js/app.js", "loadComicDemo"),
                _contains(root / "src/web/static/js/app.js", "loadResearchDemo"),
                _contains(root / "tests/test_office_preflight.py", "test_comic_production_demo_api_is_no_key_and_read_only"),
                _contains(root / "tests/test_office_preflight.py", "test_research_demo_api_is_no_key_and_read_only"),
            ],
            [
                "src/web/app.py:/api/demo/comic-production",
                "src/web/app.py:/api/demo/research",
                "src/web/static/index.html",
                "src/web/static/js/app.js",
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
            "agent_output_schema_gate",
            "Agent output schema gate",
            [
                _contains(root / "src/comic_office/v2/output_schemas.py", "comic_contract"),
                _contains(root / "src/comic_office/v2/output_schemas.py", "visual_revision"),
                _contains(root / "src/comic_office/v2/planner.py", "validate_agent_output_schema"),
                _contains(root / "tests/test_comic_v2_output_schemas.py", "test_schema_registry_exposes_comic_contract_gates"),
            ],
            [
                "src/comic_office/v2/output_schemas.py",
                "src/comic_office/v2/planner.py",
                "tests/test_comic_v2_output_schemas.py",
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
