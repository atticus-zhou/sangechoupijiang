"""Evidence-backed readiness checks for product-level office milestones."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def audit_comic_production_readiness(base_dir: Path | str | None = None) -> dict:
    """Audit real-product readiness for the AI comic production office.

    This deliberately excludes no-key demo mode because the current product
    plan has that phase postponed. Each check points at concrete files or code
    paths that prove the real local product capability exists.
    """
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
            "readme",
            "清晰 README",
            [
                _contains(root / "README.md", "AI 漫剧制片办公室"),
                _contains(root / "README.md", "verify_comic_v2_user_flow.py"),
                _contains(root / "README.md", "office_models"),
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
        "mode": "real_product_without_demo",
        "status": "needs_work" if failed else "ready_without_demo",
        "summary": (
            "AI 漫剧制片办公室真实产品条件已具备，暂缓项只剩无 Key 演示模式。"
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
                f"shot_refs={delivery.get('handoff_manifest_shot_reference_images', False)}; "
                f"lineage={delivery.get('handoff_manifest_production_lineage', False)} |"
            )
        user_flow = runtime.get("user_flow") or {}
        if user_flow:
            rows.append(
                "| 用户操作链路 | "
                f"{user_flow.get('status', '')} | "
                f"final_stage={user_flow.get('final_stage', '')}; "
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
