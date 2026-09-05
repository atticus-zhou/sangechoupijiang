"""Verify the product decision brief for research and future office expansion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_future_office_backlog import verify_future_office_backlog
from scripts.verify_research_office_readiness import verify_research_office_readiness

DOC_PATH = REPO_ROOT / "docs" / "OFFICE_EXPANSION_DECISION_BRIEF.md"

REQUIRED_MARKERS = [
    "办公室扩展决策简报",
    "AI 漫剧制片办公室",
    "研究办公室",
    "staged research demo",
    "不能宣称已经做到全自动飞瓜会员级采集",
    "decision_ready_but_not_started",
    "稳定后评估结论",
    "go/no-go",
    "评估完成，但不扩办公室",
    "继续强化补证闭环",
    "只保留为第一候选，不启动真实开发",
    "ecommerce_selection",
    "short_video_ads",
    "story_ip",
    "technical_project",
    "办公室专属 schema gate",
    "办公室专属 recovery actions",
    "public claim report",
    "python scripts/verify_research_office_readiness.py --format markdown",
    "python scripts/verify_future_office_backlog.py --format markdown",
    "python scripts/verify_release_readiness.py --format markdown",
]

EXPECTED_PRIORITY_ORDER = ["ecommerce_selection", "short_video_ads", "story_ip", "technical_project"]


def _read_doc() -> tuple[str, str | None]:
    if not DOC_PATH.exists():
        return "", "missing"
    try:
        return DOC_PATH.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as exc:
        return "", f"utf8_decode_error:{exc}"


def verify_office_expansion_decision_brief() -> dict[str, Any]:
    text, read_error = _read_doc()
    research = verify_research_office_readiness()
    future = verify_future_office_backlog()

    missing_markers = [marker for marker in REQUIRED_MARKERS if marker not in text]
    errors: list[str] = []
    if read_error:
        errors.append(f"decision brief read error: {read_error}")
    if missing_markers:
        errors.append(f"decision brief missing markers: {', '.join(missing_markers)}")
    if research.get("status") != "passed":
        errors.append("research office readiness must pass before expansion decisions are trusted")
    demo = research.get("demo_endpoint") or {}
    if demo.get("claim_level") != "staged_research_demo":
        errors.append("research office must stay declared as staged_research_demo")
    if demo.get("can_claim_full_automation") is not False:
        errors.append("research office must not claim full automation")
    if future.get("status") != "passed":
        errors.append("future office backlog verifier must pass")
    if future.get("prioritization_status") != "decision_ready_but_not_started":
        errors.append("future offices must stay decision_ready_but_not_started")
    if future.get("priority_order") != EXPECTED_PRIORITY_ORDER:
        errors.append("future office priority order must be ecommerce_selection, short_video_ads, story_ip, technical_project")
    if future.get("blocked_candidate_count") != future.get("candidate_count"):
        errors.append("all future office candidates must remain blocked until evidence is added")
    post_stability_review = _post_stability_review(research, future)
    if post_stability_review.get("status") != "evaluated_hold_expansion":
        errors.append("post-stability review must evaluate but hold expansion")

    return {
        "status": "passed" if not errors else "failed",
        "mode": "office_expansion_decision_brief",
        "summary": (
            "Research-office staging and future-office priority decisions are documented and bound to verifiers."
            if not errors
            else "Office expansion decision brief has gaps."
        ),
        "document": "docs/OFFICE_EXPANSION_DECISION_BRIEF.md",
        "line_count": len(text.splitlines()) if text else 0,
        "missing_marker_count": len(missing_markers),
        "research_claim_level": demo.get("claim_level"),
        "research_full_automation": demo.get("can_claim_full_automation"),
        "research_downloads": demo.get("download_count"),
        "future_prioritization_status": future.get("prioritization_status"),
        "future_priority_order": future.get("priority_order") or [],
        "future_blocked_candidates": f"{future.get('blocked_candidate_count')}/{future.get('candidate_count')}",
        "future_backlog_ids": future.get("backlog_ids") or [],
        "post_stability_review": post_stability_review,
        "errors": errors,
    }


def _post_stability_review(research: dict[str, Any], future: dict[str, Any]) -> dict[str, Any]:
    demo = research.get("demo_endpoint") or {}
    return {
        "status": "evaluated_hold_expansion",
        "decision": "do_not_start_new_office_yet",
        "reason": "AI 漫剧制片办公室继续做主样板；研究办公室保持 staged demo 并强化补证闭环；候选办公室先补 schema、recovery、样例交付和声明边界。",
        "research_go_no_go": {
            "decision": "showcase_ready_but_not_full_auto",
            "claim_level": demo.get("claim_level"),
            "can_claim_full_automation": demo.get("can_claim_full_automation"),
            "download_count": demo.get("download_count"),
            "next_focus": [
                "真实截图导入",
                "证据命名",
                "来源回填",
                "补证后重跑报告",
            ],
        },
        "future_go_no_go": {
            "decision": "candidate_backlog_only",
            "priority_order": future.get("priority_order") or [],
            "blocked_candidates": f"{future.get('blocked_candidate_count')}/{future.get('candidate_count')}",
            "required_before_start": [
                "office-specific schema gate",
                "office-specific recovery actions",
                "no-key sample delivery",
                "public claim report",
                "release gate evidence",
            ],
        },
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Office Expansion Decision Brief Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Summary: {payload.get('summary')}",
        "",
        f"- Document: `{payload.get('document')}`",
        f"- Lines: {payload.get('line_count')}",
        f"- Research claim: {payload.get('research_claim_level')} / full automation={payload.get('research_full_automation')}",
        f"- Research downloads: {payload.get('research_downloads')}",
        f"- Future status: {payload.get('future_prioritization_status')}",
        f"- Future priority order: {', '.join(payload.get('future_priority_order') or [])}",
        f"- Future blocked candidates: {payload.get('future_blocked_candidates')}",
        f"- Future backlog: {', '.join(payload.get('future_backlog_ids') or [])}",
    ]
    review = payload.get("post_stability_review") or {}
    research_review = review.get("research_go_no_go") or {}
    future_review = review.get("future_go_no_go") or {}
    lines.extend(
        [
            "",
            "## Post-stability Review",
            "",
            f"- Decision: `{review.get('decision', '')}`",
            f"- Status: `{review.get('status', '')}`",
            f"- Reason: {review.get('reason', '')}",
            f"- Research: `{research_review.get('decision', '')}` / claim={research_review.get('claim_level')} / full_auto={research_review.get('can_claim_full_automation')}",
            f"- Research next focus: {', '.join(research_review.get('next_focus') or [])}",
            f"- Future offices: `{future_review.get('decision', '')}` / blocked={future_review.get('blocked_candidates')}",
            f"- Required before start: {', '.join(future_review.get('required_before_start') or [])}",
        ]
    )
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()
    payload = verify_office_expansion_decision_brief()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
