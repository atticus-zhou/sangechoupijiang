"""Verify that the productization status map covers the public-release objective."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
STATUS_DOC = REPO_ROOT / "docs" / "PRODUCTIZATION_STATUS.md"


REQUIREMENTS: list[dict[str, Any]] = [
    {
        "id": "P1",
        "title": "Public portfolio demo boundary",
        "markers": [
            "个人网站和公开作品集",
            "python scripts/verify_public_demo_mode.py --format markdown",
            "/api/demo/public-showcase",
            "docs/DEPLOYMENT_MODES.md",
        ],
        "files": [
            "scripts/verify_public_demo_mode.py",
            "docs/DEPLOYMENT_MODES.md",
            "src/web/app.py",
        ],
    },
    {
        "id": "P2",
        "title": "No-key sample deliverables",
        "markers": [
            "面试官可以无 Key",
            "portfolio_embed",
            "样例 Word 画布",
            "handoff manifest",
        ],
        "files": [
            "scripts/verify_public_demo_mode.py",
            "tests/test_public_showcase_manifest.py",
            "tests/fixtures/comic_v2_sample.json",
        ],
    },
    {
        "id": "P3",
        "title": "Reproducible first run",
        "markers": [
            "从 GitHub 下载项目",
            "python scripts/verify_first_run_readiness.py --format markdown",
            "python scripts/doctor.py",
            "README.md",
        ],
        "files": [
            "scripts/verify_first_run_readiness.py",
            "scripts/doctor.py",
            "README.md",
        ],
    },
    {
        "id": "P4",
        "title": "AI comic production handoff",
        "markers": [
            "AI 漫剧制片办公室",
            "python scripts/verify_comic_v2_delivery.py --format markdown",
            "python scripts/verify_comic_v2_user_flow.py",
            "*_handoff_manifest.json",
        ],
        "files": [
            "scripts/verify_comic_v2_delivery.py",
            "scripts/verify_comic_v2_user_flow.py",
            "src/comic_office/v2/word_canvas.py",
        ],
    },
    {
        "id": "P5",
        "title": "Comic lineage, history, and recovery",
        "markers": [
            "资产身份",
            "引用链路",
            "历史追溯",
            "失败恢复",
            "python scripts/verify_product_readiness.py --format markdown --run-e2e",
        ],
        "files": [
            "scripts/verify_product_readiness.py",
            "tests/test_comic_v2_user_flow_verifier.py",
            "tests/test_comic_production_chain.py",
        ],
    },
    {
        "id": "P6",
        "title": "Research staged demo honesty",
        "markers": [
            "研究办公室",
            "不伪装成全自动",
            "python scripts/verify_research_office_readiness.py --format markdown",
            "证据 manifest",
        ],
        "files": [
            "scripts/verify_research_office_readiness.py",
            "tests/fixtures/research_sample.json",
            "tests/test_research_office_readiness_verifier.py",
        ],
    },
    {
        "id": "P7",
        "title": "Office isolation and extension governance",
        "markers": [
            "新办公室",
            "python scripts/verify_office_isolation.py --format markdown",
            "python scripts/verify_office_extension_governance.py --format markdown",
            "/api/offices/protocols",
        ],
        "files": [
            "scripts/verify_office_isolation.py",
            "scripts/verify_office_extension_governance.py",
            "src/offices.py",
        ],
    },
    {
        "id": "P8",
        "title": "Secret and runtime artifact safety",
        "markers": [
            "公开仓库不应包含用户密钥",
            "python scripts/check_no_secrets.py",
            ".gitignore",
            "docs/DEPLOYMENT_MODES.md",
        ],
        "files": [
            "scripts/check_no_secrets.py",
            ".gitignore",
            "docs/DEPLOYMENT_MODES.md",
        ],
    },
    {
        "id": "P9",
        "title": "Model configuration guidance",
        "markers": [
            "新用户能看懂每个部门需要什么模型",
            "docs/MODEL_CONFIGURATION.md",
            "python scripts/verify_model_configuration_guidance.py --format markdown",
            "最小可跑",
            "完整制片",
        ],
        "files": [
            "docs/MODEL_CONFIGURATION.md",
            "scripts/verify_model_configuration_guidance.py",
            "tests/test_model_configuration_guidance.py",
        ],
    },
]


def verify_productization_status() -> dict[str, Any]:
    errors: list[str] = []
    if not STATUS_DOC.exists():
        return {
            "status": "failed",
            "summary": "docs/PRODUCTIZATION_STATUS.md is missing.",
            "requirements": [],
            "errors": ["missing status doc"],
        }

    text = STATUS_DOC.read_text(encoding="utf-8")
    requirements: list[dict[str, Any]] = []
    for item in REQUIREMENTS:
        missing_markers = [marker for marker in item["markers"] if marker not in text]
        missing_files = [path for path in item["files"] if not (REPO_ROOT / path).exists()]
        passed = not missing_markers and not missing_files
        if not passed:
            errors.append(item["id"])
        requirements.append(
            {
                "id": item["id"],
                "title": item["title"],
                "status": "passed" if passed else "failed",
                "missing_markers": missing_markers,
                "missing_files": missing_files,
                "evidence_files": item["files"],
            }
        )

    release_script = (REPO_ROOT / "scripts" / "verify_release_readiness.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    release_includes_status = "verify_productization_status.py" in release_script
    if not release_includes_status:
        errors.append("release_gate_missing_productization_status")

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
    readme_links_status = "docs/PRODUCTIZATION_STATUS.md" in readme
    if not readme_links_status:
        errors.append("readme_missing_productization_status")

    return {
        "status": "passed" if not errors else "failed",
        "summary": (
            "Productization objective coverage is documented and linked to gates."
            if not errors
            else f"{len(errors)} productization coverage checks failed."
        ),
        "document": "docs/PRODUCTIZATION_STATUS.md",
        "release_gate_includes_status": release_includes_status,
        "readme_links_status": readme_links_status,
        "requirements": requirements,
        "errors": errors,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Productization Status Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Document: `{payload.get('document', 'docs/PRODUCTIZATION_STATUS.md')}`",
        f"Summary: {payload.get('summary')}",
        f"Release gate includes this audit: `{payload.get('release_gate_includes_status')}`",
        f"README links this audit: `{payload.get('readme_links_status')}`",
        "",
        "| Requirement | Status | Evidence files |",
        "| --- | --- | --- |",
    ]
    for item in payload.get("requirements", []):
        files = ", ".join(f"`{path}`" for path in item.get("evidence_files", []))
        lines.append(f"| {item.get('id')} {item.get('title')} | {item.get('status')} | {files} |")
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        for item in payload["requirements"]:
            if item.get("status") == "passed":
                continue
            lines.append(f"- {item['id']}: missing markers={item['missing_markers']}; missing files={item['missing_files']}")
        for error in payload["errors"]:
            if str(error).startswith("P"):
                continue
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify productization objective coverage.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = verify_productization_status()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
