"""Verify model-configuration guidance without reading real user keys."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE = REPO_ROOT / "docs" / "MODEL_CONFIGURATION.md"
MATRIX = REPO_ROOT / "docs" / "MODEL_CAPABILITY_MATRIX.json"


CHECKS: list[dict[str, Any]] = [
    {
        "id": "guide_exists",
        "title": "Model configuration guide exists",
        "file": GUIDE,
        "markers": [
            "公开无 Key 演示",
            "最小可跑配置",
            "完整制片配置",
            "办公室隔离规则",
            "python scripts/verify_model_configuration_guidance.py --format markdown",
            "docs/MODEL_CAPABILITY_MATRIX.json",
        ],
    },
    {
        "id": "capability_matrix_exists",
        "title": "Machine-readable model capability matrix exists",
        "file": MATRIX,
        "markers": [
            "three_cobblers_model_capability_matrix_v1",
            "safe_key_rule",
            "comic_production",
            "research",
            "image_generation",
            "vision_understanding",
            "browser_or_human_evidence",
        ],
    },
    {
        "id": "department_capability_table",
        "title": "Guide explains department model kinds and missing impact",
        "file": GUIDE,
        "markers": [
            "内阁",
            "中书省",
            "兵部",
            "刑部",
            "工部",
            "视觉理解模型",
            "生图模型",
            "缺失影响",
        ],
    },
    {
        "id": "safe_key_storage",
        "title": "Guide explains safe key storage",
        "file": GUIDE,
        "markers": [
            "DEEPSEEK_API_KEY",
            "DASHSCOPE_API_KEY",
            "ARK_API_KEY",
            "config.yaml",
            ".gitignore",
            "不要提交真实 Key",
        ],
    },
    {
        "id": "example_config_has_office_overrides",
        "title": "config.example.yaml demonstrates office-scoped model overrides",
        "file": REPO_ROOT / "config.example.yaml",
        "markers": [
            "office_models:",
            "comic_production:",
            "bingbu:",
            "deepseek-chat",
            "doubao-seedream-5",
            "qwen-vl-max",
            "${DEEPSEEK_API_KEY}",
            "${ARK_API_KEY}",
            "${DASHSCOPE_API_KEY}",
        ],
    },
    {
        "id": "comic_department_examples_match_runtime_roles",
        "title": "AI comic example config keeps Bingbu text, Gongbu image, and Xingbu vision",
        "file": REPO_ROOT / "config.example.yaml",
        "markers": [
            "comic_production:",
            "bingbu:\n      provider: deepseek\n      model: deepseek-chat",
            "gongbu:\n      provider: doubao\n      model: doubao-seedream-5",
            "xingbu:\n      provider: dashscope\n      model: qwen-vl-max",
        ],
    },
    {
        "id": "readme_links_guide",
        "title": "README links to the detailed model guide",
        "file": REPO_ROOT / "README.md",
        "markers": [
            "docs/MODEL_CONFIGURATION.md",
            "verify_model_configuration_guidance.py",
        ],
    },
    {
        "id": "guide_warns_common_model_misfills",
        "title": "Guide warns about common text/image/vision misfills",
        "file": GUIDE,
        "markers": [
            "常见误填",
            "把豆包 Seedream 填到兵部",
            "兵部填 DeepSeek Chat、Qwen 文本模型或 GPT 文本模型",
            "把 DeepSeek 填到 AI 漫剧制片办公室工部后期待它生图",
            "office_models.comic_production.gongbu",
            "当前优先作为生图槽位使用",
            "文本规划交给中书省、兵部等文本部门",
            "把普通文本模型填到刑部后期待它看图",
        ],
    },
    {
        "id": "frontend_explains_requirements",
        "title": "Model page explains requirements, tests, and impact",
        "file": REPO_ROOT / "src" / "web" / "static" / "js" / "app.js",
        "markers": [
            "MODEL_REQUIREMENTS",
            "MODEL_REQUIREMENT_GROUPS",
            "modelRequirementImpact",
            "测试此部门",
            "测试当前办公室全部部门",
            "生图模型",
            "视觉理解",
            "Word 制片画布会复用已确认文本、提示词包和本地组装链路",
            "缺失影响",
        ],
    },
    {
        "id": "preflight_checks_model_kinds",
        "title": "Office preflight distinguishes text, image, and vision capabilities",
        "file": REPO_ROOT / "src" / "office_preflight.py",
        "markers": [
            "文本模型",
            "生图模型",
            "视觉模型",
            "_is_text_ready",
            "_is_vision_ready",
            "is_image_generation_config",
            "打开模型页面",
        ],
    },
]


def _matrix_checks() -> list[dict[str, Any]]:
    file_label = str(MATRIX.relative_to(REPO_ROOT))
    if not MATRIX.exists():
        return [
            {
                "id": "capability_matrix_semantics",
                "title": "Capability matrix maps offices, departments, and model kinds",
                "status": "failed",
                "file": file_label,
                "missing_file": file_label,
                "missing_markers": ["file missing"],
            }
        ]

    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    missing: list[str] = []
    if matrix.get("schema") != "three_cobblers_model_capability_matrix_v1":
        missing.append("schema")
    if "API keys" not in matrix.get("safe_key_rule", ""):
        missing.append("safe_key_rule")

    kinds = set((matrix.get("capability_kinds") or {}).keys())
    for required in {"text", "image_generation", "vision_understanding", "browser_or_human_evidence"}:
        if required not in kinds:
            missing.append(f"capability_kind:{required}")

    offices = matrix.get("offices") or {}
    comic_departments = {
        item.get("department_id"): item.get("required_capability")
        for item in offices.get("comic_production", {}).get("departments", [])
    }
    for department_id, capability in {
        "cabinet": "text",
        "zhongshu": "text",
        "menxia": "text",
        "hubu": "text",
        "bingbu": "text",
        "gongbu": "image_generation",
        "xingbu": "vision_understanding",
        "libu": "text",
    }.items():
        if comic_departments.get(department_id) != capability:
            missing.append(f"comic_production.{department_id}:{capability}")

    research_departments = {
        item.get("department_id"): item.get("required_capability")
        for item in offices.get("research", {}).get("departments", [])
    }
    for department_id in ("zhongshu", "menxia", "hubu", "bingbu"):
        if research_departments.get(department_id) != "text":
            missing.append(f"research.{department_id}:text")
    if research_departments.get("gongbu") != "browser_or_human_evidence":
        missing.append("research.gongbu:browser_or_human_evidence")

    for office_id, office in offices.items():
        for department in office.get("departments", []):
            for field in ("department_id", "display_name", "required_capability", "human_test_label", "missing_impact"):
                if not department.get(field):
                    missing.append(f"{office_id}.{department.get('department_id', 'unknown')}.{field}")

    return [
        {
            "id": "capability_matrix_semantics",
            "title": "Capability matrix maps offices, departments, and model kinds",
            "status": "passed" if not missing else "failed",
            "file": file_label,
            "missing_file": "",
            "missing_markers": missing,
        }
    ]


def verify_model_configuration_guidance() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for check in CHECKS:
        path = Path(check["file"])
        if not path.exists():
            missing_markers = list(check["markers"])
            missing_file = str(path.relative_to(REPO_ROOT))
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
            missing_markers = [marker for marker in check["markers"] if marker not in text]
            missing_file = ""
        passed = not missing_file and not missing_markers
        if not passed:
            failures.append(check["id"])
        results.append(
            {
                "id": check["id"],
                "title": check["title"],
                "status": "passed" if passed else "failed",
                "file": str(path.relative_to(REPO_ROOT)),
                "missing_file": missing_file,
                "missing_markers": missing_markers,
            }
        )
    for item in _matrix_checks():
        if item["status"] != "passed":
            failures.append(item["id"])
        results.append(item)
    return {
        "status": "passed" if not failures else "failed",
        "mode": "model_configuration_guidance",
        "summary": (
            "Model configuration guidance is documented and aligned with runtime checks."
            if not failures
            else f"{len(failures)} model guidance checks failed."
        ),
        "checks": results,
        "failures": failures,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Model Configuration Guidance Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Summary: {payload.get('summary')}",
        "",
        "| Check | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for item in payload.get("checks", []):
        lines.append(
            f"| {item.get('title')} | {item.get('status')} | `{item.get('file')}` |"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for item in payload.get("checks", []):
            if item.get("status") == "passed":
                continue
            lines.append(
                f"- {item.get('id')}: missing_file={item.get('missing_file')}; "
                f"missing_markers={item.get('missing_markers')}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify model configuration guidance.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = verify_model_configuration_guidance()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
