"""Public claim helpers for AI comic production handoffs."""

from __future__ import annotations

from typing import Any


def claim_level_from_benchmark(benchmark: dict[str, Any]) -> str:
    """Return the public claim level implied by a quality benchmark."""
    if benchmark.get("production_quality_verified"):
        return "real_quality_verified"
    if benchmark.get("status") == "demo_structure_verified" and benchmark.get("package_quality_ready"):
        return "demo_structure_only"
    return "needs_review"


def claim_upgrade_checklist(claim_level: str, benchmark: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe evidence needed before a stronger public quality claim is allowed."""
    visual_level = str(benchmark.get("visual_evidence_level") or "unknown")
    stored_matches = bool(benchmark.get("stored_benchmark_matches"))
    production_verified = bool(benchmark.get("production_quality_verified"))
    package_ready = bool(benchmark.get("package_quality_ready"))
    if claim_level == "real_quality_verified":
        return [
            {
                "id": "keep_evidence_bundle",
                "title": "\u4fdd\u7559\u771f\u5b9e\u8d28\u91cf\u8bc1\u636e\u5305",
                "status": "complete",
                "required_evidence": [
                    "handoff manifest",
                    "Word \u5236\u7247\u753b\u5e03",
                    "\u8d28\u91cf\u57fa\u51c6\u62a5\u544a",
                    "\u771f\u5b9e\u6a21\u578b\u56fe\u7247\u8bb0\u5f55",
                ],
                "why_it_matters": (
                    "\u540e\u7eed\u516c\u5f00\u5c55\u793a\u3001\u590d\u76d8\u6216\u4ea4\u7ed9\u4e0b\u6e38\u65f6\uff0c"
                    "\u53ef\u4ee5\u8bc1\u660e\u8fd9\u4e0d\u662f fixture \u6837\u4f8b\u6216\u53e3\u5934\u58f0\u660e\u3002"
                ),
            },
            {
                "id": "repeat_after_major_edit",
                "title": "\u91cd\u5927\u6539\u52a8\u540e\u91cd\u65b0\u9a8c\u8bc1",
                "status": "required_when_changed",
                "required_evidence": [
                    "\u65b0\u7684 manifest",
                    "\u65b0\u7684\u8d28\u91cf\u57fa\u51c6",
                    "\u65b0\u7684\u771f\u5b9e\u751f\u4ea7\u58f0\u660e\u62a5\u544a",
                ],
                "why_it_matters": (
                    "\u6545\u4e8b\u3001\u8d44\u4ea7\u3001\u6a21\u578b\u6216\u63d0\u793a\u8bcd\u53d8\u66f4\u540e\uff0c"
                    "\u65e7\u8d28\u91cf\u58f0\u660e\u4e0d\u80fd\u81ea\u52a8\u7ee7\u627f\u3002"
                ),
            },
        ]
    if claim_level == "demo_structure_only":
        return [
            {
                "id": "run_real_models",
                "title": "\u4f7f\u7528\u771f\u5b9e\u6a21\u578b\u751f\u6210\u56fe\u7247\u8d44\u4ea7",
                "status": "missing",
                "required_evidence": [
                    "\u975e fixture \u56fe\u7247",
                    "provider",
                    "model",
                    "image_id",
                    "\u751f\u6210\u65f6\u95f4\u6216\u751f\u4ea7\u8bb0\u5f55",
                ],
                "why_it_matters": (
                    "\u56fa\u5b9a\u6837\u4f8b\u53ea\u80fd\u8bc1\u660e\u7ed3\u6784\uff0c"
                    "\u4e0d\u80fd\u8bc1\u660e\u771f\u5b9e\u6a21\u578b\u753b\u98ce\u3001\u4eba\u7269\u4e00\u81f4\u6027\u6216\u8d44\u4ea7\u53ef\u7528\u6027\u3002"
                ),
            },
            {
                "id": "visual_review",
                "title": "\u6267\u884c\u771f\u5b9e\u89c6\u89c9\u8d28\u68c0",
                "status": "missing" if visual_level != "model_reviewed" else "complete",
                "required_evidence": [
                    "review.status=pass",
                    "handoff_ready=true",
                    "fixture=false",
                    "\u5404\u7ef4\u5ea6\u5206\u6570",
                ],
                "why_it_matters": (
                    "\u53ea\u6709\u89c6\u89c9\u8d28\u68c0\u901a\u8fc7\uff0c"
                    "\u624d\u80fd\u628a\u4eba\u7269\u3001\u9053\u5177\u3001\u573a\u666f\u548c\u753b\u98ce\u4e00\u81f4\u6027\u4f5c\u4e3a\u516c\u5f00\u8d28\u91cf\u8bc1\u636e\u3002"
                ),
            },
            {
                "id": "stored_benchmark",
                "title": "\u91cd\u65b0\u5199\u5165\u5e76\u590d\u6838\u8d28\u91cf\u57fa\u51c6",
                "status": (
                    "complete"
                    if stored_matches and production_verified
                    else "structure_only"
                    if stored_matches
                    else "missing"
                ),
                "required_evidence": [
                    "quality_benchmark",
                    "stored_benchmark_matches=true",
                    "production_quality_verified=true",
                ],
                "why_it_matters": (
                    "\u516c\u5f00\u58f0\u660e\u5fc5\u987b\u6765\u81ea\u5f53\u524d manifest \u7684\u673a\u5668\u53ef\u590d\u6838\u57fa\u51c6\uff0c"
                    "\u800c\u4e0d\u662f\u4eba\u5de5\u53e3\u5934\u5224\u65ad\u3002"
                ),
            },
        ]
    recovery = benchmark.get("recommended_recovery") or {}
    return [
        {
            "id": "resolve_blockers",
            "title": "\u5148\u5904\u7406\u963b\u585e\u9879",
            "status": "missing",
            "required_evidence": [
                "quality_benchmark.issues",
                "recommended_recovery",
                "\u8d23\u4efb\u90e8\u95e8\u4fee\u590d\u8bb0\u5f55",
            ],
            "why_it_matters": (
                "\u5b58\u5728 blocker \u65f6\uff0c\u5236\u7247\u5305\u4e0d\u80fd\u5f53\u6210\u53ef\u4ea4\u4ed8\u6750\u6599\uff0c"
                "\u4e5f\u4e0d\u80fd\u8fdb\u5165\u771f\u5b9e\u8d28\u91cf\u58f0\u660e\u3002"
            ),
        },
        {
            "id": "rerun_benchmark",
            "title": "\u4fee\u590d\u540e\u91cd\u8dd1\u8d28\u91cf\u57fa\u51c6",
            "status": "missing" if not package_ready else "partial",
            "required_evidence": [
                "package_quality_ready=true",
                "blocker_count=0",
                "\u65b0\u7684 claim report",
            ],
            "why_it_matters": str(
                recovery.get("description")
                or benchmark.get("next_action")
                or "\u9700\u8981\u7528\u65b0\u7684\u8d28\u91cf\u57fa\u51c6\u8bc1\u660e\u963b\u585e\u9879\u5df2\u7ecf\u5904\u7406\u3002"
            ),
        },
        {
            "id": "upgrade_visual_evidence",
            "title": "\u8865\u9f50\u771f\u5b9e\u89c6\u89c9\u8bc1\u636e",
            "status": "missing" if not production_verified else "complete",
            "required_evidence": [
                "model_reviewed \u56fe\u7247",
                "\u89c6\u89c9\u8d28\u68c0\u901a\u8fc7",
                "production_quality_verified=true",
            ],
            "why_it_matters": (
                "\u5373\u4f7f\u7ed3\u6784\u4fee\u597d\uff0c"
                "\u6ca1\u6709\u771f\u5b9e\u89c6\u89c9\u8bc1\u636e\u4e5f\u4e0d\u80fd\u5ba3\u79f0\u771f\u5b9e\u6a21\u578b\u753b\u8d28\u901a\u8fc7\u3002"
            ),
        },
    ]
