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
            "OPENAI_API_KEY",
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
            "Provider 怎么填",
            "阿里云百炼/通义千问 API Key",
            "火山方舟/豆包 Seedream API Key",
            "千问 VL",
        ],
    },
    {
        "id": "frontend_explains_requirements",
        "title": "Model page explains requirements, tests, and impact",
        "file": REPO_ROOT / "src" / "web" / "static" / "js" / "app.js",
        "markers": [
            "MODEL_REQUIREMENTS",
            "MODEL_REQUIREMENT_GROUPS",
            "loadModelCapabilityContract",
            "modelRequirementFromContract",
            "capabilityContractDepartment",
            "model-contract-source",
            "model-contract-modes",
            "minimum_ready_when",
            "full_ready_when",
            "/api/offices/${officeId}/model-capabilities",
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
            "summarize_office_capability_contract",
            "model_capability_contract",
            "文本模型",
            "生图模型",
            "视觉模型",
            "_is_text_ready",
            "_is_vision_ready",
            "is_image_generation_config",
            "打开模型页面",
        ],
    },
    {
        "id": "capability_matrix_api",
        "title": "Backend exposes the no-key capability matrix for UI and future offices",
        "file": REPO_ROOT / "src" / "web" / "app.py",
        "markers": [
            "/api/model-capability-matrix",
            "/api/offices/{office_id}/model-capabilities",
            "load_model_capability_matrix",
            "get_office_capability_contract",
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
        "zhongshu": "text",
        "menxia": "text",
        "shangshu": "text",
        "libu": "text",
        "hubu": "text",
        "bingbu": "text",
        "gongbu": "image_generation",
        "xingbu": "vision_understanding",
        "libu_comm": "text",
    }.items():
        if comic_departments.get(department_id) != capability:
            missing.append(f"comic_production.{department_id}:{capability}")

    research_departments = {
        item.get("department_id"): item.get("required_capability")
        for item in offices.get("research", {}).get("departments", [])
    }
    for department_id in ("zhongshu", "menxia", "shangshu", "libu", "hubu", "libu_comm", "bingbu"):
        if research_departments.get(department_id) != "text":
            missing.append(f"research.{department_id}:text")
    if research_departments.get("xingbu") != "vision_understanding":
        missing.append("research.xingbu:vision_understanding")
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


def _group_departments_by_capability(departments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for department in departments:
        kind = str(department.get("required_capability") or "unknown")
        grouped.setdefault(kind, []).append(
            {
                "department_id": department.get("department_id", ""),
                "display_name": department.get("display_name", ""),
                "human_test_label": department.get("human_test_label", ""),
                "missing_impact": department.get("missing_impact", ""),
                "required_for": list(department.get("required_for") or []),
            }
        )
    return grouped


def _office_model_setup_summary(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    capability_kinds = matrix.get("capability_kinds") or {}
    for office_id, office in sorted((matrix.get("offices") or {}).items()):
        departments = list(office.get("departments") or [])
        grouped = _group_departments_by_capability(departments)
        capability_counts = {kind: len(items) for kind, items in grouped.items()}
        summaries.append(
            {
                "office_id": office_id,
                "office_name": office.get("office_name", office_id),
                "minimum_mode": office.get("minimum_mode", ""),
                "full_mode": office.get("full_mode", ""),
                "department_count": len(departments),
                "capability_counts": capability_counts,
                "departments_by_capability": grouped,
                "requires_image_generation": "image_generation" in grouped,
                "requires_vision_understanding": "vision_understanding" in grouped,
                "requires_browser_or_human_evidence": "browser_or_human_evidence" in grouped,
                "minimum_ready_when": office.get("minimum_ready_when", ""),
                "full_ready_when": office.get("full_ready_when", ""),
                "capability_labels": {
                    kind: (capability_kinds.get(kind) or {}).get("label", kind)
                    for kind in grouped
                },
            }
        )
    return summaries


def _comic_setup_ladder(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    comic = (matrix.get("offices") or {}).get("comic_production") or {}
    grouped = _group_departments_by_capability(list(comic.get("departments") or []))
    text_departments = [item["department_id"] for item in grouped.get("text", [])]
    image_departments = [item["department_id"] for item in grouped.get("image_generation", [])]
    vision_departments = [item["department_id"] for item in grouped.get("vision_understanding", [])]
    return [
        {
            "level": "no_key_demo",
            "requires_api_key": False,
            "required_departments": [],
            "can_do": "查看公开固定样例、下载示例交付物、理解产品流程边界。",
            "ready_when": "public demo/static showcase gates pass; no real model calls and no real user keys.",
        },
        {
            "level": "minimum_text",
            "requires_api_key": True,
            "required_departments": text_departments,
            "can_do": comic.get(
                "minimum_ready_when",
                "完成故事、资产、镜头和提示词包的文本规划。",
            ),
            "missing_impact": "缺少这些文本部门时，用户会在聊故事、拆资产、提示词规划或 Word 文案阶段卡住。",
        },
        {
            "level": "full_comic_production",
            "requires_api_key": True,
            "required_departments": image_departments + vision_departments,
            "can_do": comic.get(
                "full_ready_when",
                "生成基础资产图、执行视觉质检，并输出完整 Word 制片画布。",
            ),
            "missing_impact": "缺少工部或刑部时，可以保留文本制片包，但不能宣称完成真实图片生产和视觉质检。",
        },
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
    matrix_payload = json.loads(MATRIX.read_text(encoding="utf-8")) if MATRIX.exists() else {}
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
        "office_model_setup_summary": _office_model_setup_summary(matrix_payload),
        "comic_setup_ladder": _comic_setup_ladder(matrix_payload),
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
    summaries = payload.get("office_model_setup_summary") or []
    if summaries:
        lines.extend(["", "## Office Model Setup Summary", ""])
        for office in summaries:
            counts = ", ".join(
                f"{kind}={count}"
                for kind, count in sorted((office.get("capability_counts") or {}).items())
            )
            lines.extend(
                [
                    f"### {office.get('office_name')} (`{office.get('office_id')}`)",
                    "",
                    f"- Minimum mode: `{office.get('minimum_mode')}`",
                    f"- Full mode: `{office.get('full_mode')}`",
                    f"- Departments: `{office.get('department_count')}`; capabilities: {counts}",
                    f"- Minimum ready when: {office.get('minimum_ready_when')}",
                    f"- Full ready when: {office.get('full_ready_when')}",
                    "",
                    "| Capability | Departments | Human test | Missing impact |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for kind, departments in sorted((office.get("departments_by_capability") or {}).items()):
                labels = office.get("capability_labels") or {}
                department_names = "、".join(
                    f"{item.get('display_name')} `{item.get('department_id')}`"
                    for item in departments
                )
                tests = "；".join(item.get("human_test_label", "") for item in departments)
                impacts = "；".join(item.get("missing_impact", "") for item in departments)
                lines.append(
                    f"| {labels.get(kind, kind)} `{kind}` | {department_names} | {tests} | {impacts} |"
                )
            lines.append("")
    ladder = payload.get("comic_setup_ladder") or []
    if ladder:
        lines.extend(["## AI Comic Setup Ladder", ""])
        for item in ladder:
            departments = ", ".join(item.get("required_departments") or []) or "none"
            lines.extend(
                [
                    f"### `{item.get('level')}`",
                    "",
                    f"- Requires API key: `{item.get('requires_api_key')}`",
                    f"- Required departments: {departments}",
                    f"- Can do: {item.get('can_do')}",
                    f"- Missing impact: {item.get('missing_impact', item.get('ready_when', ''))}",
                    "",
                ]
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
