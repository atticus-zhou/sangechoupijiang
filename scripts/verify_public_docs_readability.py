"""Verify that public-facing docs stay readable and release-oriented."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_DOCS: list[dict[str, Any]] = [
    {
        "path": "README.md",
        "role": "GitHub front door",
        "required_markers": [
            "# 三个臭皮匠",
            "本地优先的多 Agent 协作工作台",
            "公开无 Key 演示",
            "本地真实使用",
            "AI 漫剧制片办公室",
            "研究办公室",
            "公开展示与部署边界",
            "线上 URL 只有在 `npm run check:online` 通过后，才能说已经部署成功",
            "文本模型、图片生成模型、视觉理解模型是不同能力，不要混填",
            "# 三个臭皮匠",
            "三类读者怎么体验",
            "docs/FIRST_RUN_DECISION_CARD.md",
            "公开演示和部署边界",
            "真实生产声明",
            "模型台阶可以这样理解",
            "AI 漫剧真实生产声明报告",
            "下游生产 quick-start",
            "docs/NEW_OFFICE_STARTER_CHECKLIST.md",
            "python scripts/verify_release_readiness.py --format markdown",
            "python scripts/verify_development_checklist.py --format markdown",
            "python scripts/verify_public_docs_readability.py --format markdown",
            "python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase",
            "python scripts/verify_future_office_backlog.py --format markdown",
            "python scripts/export_office_creation_template.py --format markdown",
            "data/comic_production_claim_report.json",
            "claim_upgrade_recovery",
        ],
    },
    {
        "path": "docs/FIRST_RUN_DECISION_CARD.md",
        "role": "first-run decision card",
        "required_markers": [
            "首次运行决策卡",
            "先选一条路",
            "面试官或访客",
            "本地真实用户",
            "开发者",
            "python scripts/export_public_showcase.py",
            "python run.py --port 8080",
            "工部",
            "刑部",
            "office_id",
            "python scripts/check_no_secrets.py",
            "不要提交到公开仓库",
        ],
    },
    {
        "path": "docs/DEPLOYMENT_MODES.md",
        "role": "deployment boundary",
        "required_markers": [
            "演示模式",
            "本地真实模式",
            "不要把个人 API Key 写入前端",
            "python scripts/verify_public_demo_mode.py --format markdown",
            "python scripts/verify_static_public_showcase.py --format markdown",
        ],
    },
    {
        "path": "docs/PUBLIC_RELEASE_HANDOFF.md",
        "role": "public handoff checklist",
        "required_markers": [
            "/api/demo/public-showcase",
            "dist/public-showcase",
            "python scripts/verify_first_run_readiness.py --format markdown",
            "python scripts/verify_release_readiness.py --format markdown",
            "python scripts/verify_public_comic_trace_bundle.py --format markdown",
            "data/comic_production_claim_report.json",
            "claim_upgrade_recovery",
            "regenerate_images",
            "python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase",
            "七份下载物",
            "下游生产 quick-start",
        ],
    },
    {
        "path": "docs/PRODUCTIZATION_STATUS.md",
        "role": "objective evidence map",
        "required_markers": [
            "产品化状态审计",
            "任何对外说法都必须能落到一个可运行命令",
            "AI 漫剧制片办公室",
            "研究办公室",
            "线上证明只认",
            "不能证明 Vercel 线上页面已经更新",
            "产品化状态表",
            "python scripts/verify_productization_status.py --format markdown",
            "python scripts/verify_release_readiness.py --format markdown",
            "P10",
        ],
    },
    {
        "path": "docs/PRODUCT_EVOLUTION_TASKLIST.md",
        "role": "mission-critical evolution tasklist",
        "required_markers": [
            "\u4e09\u4e2a\u81ed\u76ae\u5320\u4ea7\u54c1\u8fdb\u5316\u4efb\u52a1\u6e05\u5355",
            "\u7b2c\u4e00\u4f18\u5148\u7ea7\u7ea6\u675f",
            "\u957f\u671f\u76ee\u6807",
            "\u9636\u6bb5 A\uff1a\u53ef\u4fe1\u5c55\u793a",
            "\u9636\u6bb5 B\uff1a\u5355\u529e\u516c\u5ba4\u4ea7\u54c1\u7ea7",
            "\u9636\u6bb5 C\uff1a\u5e73\u53f0\u534f\u8bae\u5316",
            "\u9636\u6bb5 D\uff1a\u771f\u5b9e\u4f7f\u7528\u95ed\u73af",
            "\u9636\u6bb5 E\uff1a\u591a\u529e\u516c\u5ba4\u6269\u5c55",
            "python scripts/verify_development_checklist.py --format markdown",
            "python scripts/verify_release_readiness.py --format markdown",
            "python scripts/export_office_creation_template.py --format markdown",
            "image_quality_summary",
            "future_schema_validators",
        ],
    },
    {
        "path": "docs/STATIC_SHOWCASE_DEPLOYMENT.md",
        "role": "static showcase deploy guide",
        "required_markers": [
            "python scripts/export_public_showcase.py",
            "python scripts/verify_static_public_showcase.py --format markdown",
            "python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase",
            "dist/public-showcase/index.html",
            "npx vercel --prod --cwd dist/public-showcase",
            "data/comic_production_claim_report.json",
            "claim_upgrade_recovery",
            "regenerate_images",
            "七份样例下载物",
            "下游生产 quick-start",
        ],
    },
    {
        "path": "docs/REAL_PRODUCTION_CLAIMS.md",
        "role": "claim boundary",
        "required_markers": [
            "demo_structure_only",
            "production_quality_verified",
            "claim_upgrade_checklist",
            "claim_upgrade_recovery",
            "image_production_evidence",
            "image_quality_summary",
            "rework_instructions",
            "regenerate_images",
            "python scripts/verify_comic_real_production_claim.py --format markdown",
        ],
    },
    {
        "path": "docs/COMIC_DOWNSTREAM_HANDOFF.md",
        "role": "comic downstream handoff",
        "required_markers": [
            "Word 制片画布",
            "handoff manifest",
            "python scripts/verify_comic_v2_downstream_handoff.py --format markdown",
            "production_quality_verified=False",
            "image_production_evidence",
            "image_quality_summary",
            "rework_instructions",
            "regenerate_images",
            "first_frame_reference_image",
            "reference_asset_chain",
            "director_execution",
        ],
    },
    {
        "path": "docs/NEW_OFFICE_STARTER_CHECKLIST.md",
        "role": "new office starter checklist",
        "required_markers": [
            "New Office Starter Checklist",
            "office_id",
            "downloadable_deliverables",
            "public_safety_boundaries",
            "verify_office_extension_governance",
            "verify_release_readiness",
            "check_no_secrets",
        ],
    },
]

SUSPICIOUS_TEXT_MARKERS = [
    "\ufffd",
    "\u951f",
    "\u95bf",
    "\u00c3",
    "\u00c2",
    "\u00ef\u00bf\u00bd",
    "\u6d93\u5909\u91dc",
    "\u9477",
    "\u936b\u70b2",
    "\u5a55\u65d7",
    "\u9422\u7197",
    "\u7a0b\u5b08",
    "\u675e\u64b3",
    "\u95c8\u5822",
    "\u6d63\u8de8",
]


def _find_suspicious_markers(text: str) -> list[str]:
    return [marker for marker in SUSPICIOUS_TEXT_MARKERS if marker in text]


def _read_doc(path: Path) -> tuple[str | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as exc:
        return None, f"utf8_decode_error:{exc}"


def verify_public_docs_readability() -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    failures: list[str] = []

    for spec in PUBLIC_DOCS:
        relative_path = spec["path"]
        text, read_error = _read_doc(REPO_ROOT / relative_path)
        suspicious = []
        missing_markers = list(spec["required_markers"])
        status = "failed"
        line_count = 0

        if text is not None:
            suspicious = _find_suspicious_markers(text)
            missing_markers = [marker for marker in spec["required_markers"] if marker not in text]
            line_count = len(text.splitlines())
            status = "passed" if not suspicious and not missing_markers else "failed"

        if read_error or status != "passed":
            failures.append(relative_path)

        docs.append(
            {
                "path": relative_path,
                "role": spec["role"],
                "status": status,
                "line_count": line_count,
                "read_error": read_error,
                "suspicious_markers": suspicious,
                "missing_markers": missing_markers,
            }
        )

    return {
        "status": "passed" if not failures else "failed",
        "mode": "public_docs_readability",
        "summary": (
            "Public docs are UTF-8 readable and include release handoff markers."
            if not failures
            else f"{len(failures)} public docs readability checks failed."
        ),
        "doc_count": len(docs),
        "passed_count": len([item for item in docs if item["status"] == "passed"]),
        "failed_count": len(failures),
        "docs": docs,
        "failures": failures,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Public Docs Readability Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Summary: {payload.get('summary')}",
        f"Docs: `{payload.get('passed_count')}/{payload.get('doc_count')}`",
        "",
        "| Document | Status | Role | Lines |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload.get("docs", []):
        lines.append(
            f"| `{item.get('path')}` | {item.get('status')} | "
            f"{item.get('role')} | {item.get('line_count')} |"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for item in payload.get("docs", []):
            if item.get("status") == "passed":
                continue
            lines.append(f"### {item.get('path')}")
            if item.get("read_error"):
                lines.append(f"- read_error: {item.get('read_error')}")
            if item.get("suspicious_markers"):
                lines.append(f"- suspicious_markers: {item.get('suspicious_markers')}")
            if item.get("missing_markers"):
                lines.append(f"- missing_markers: {item.get('missing_markers')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify public docs readability.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    payload = verify_public_docs_readability()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
