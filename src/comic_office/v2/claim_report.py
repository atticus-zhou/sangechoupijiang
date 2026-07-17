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


def claim_upgrade_recovery(claim_level: str, benchmark: dict[str, Any]) -> dict[str, Any]:
    """Return an operator playbook for moving a demo claim toward real quality evidence."""
    visual_level = str(benchmark.get("visual_evidence_level") or "unknown")
    if claim_level == "real_quality_verified":
        return {
            "required": False,
            "reason": "当前 handoff manifest 已经具备真实模型图片和视觉质检证据。",
            "next_action": "保留 Word、handoff manifest、质量基准和 claim report 作为公开证据包。",
            "recovery_action": "",
            "recovery_endpoint": "",
            "preserves": [
                "confirmed_story",
                "asset_manifest",
                "prompt_package",
                "image_production_evidence",
                "visual_review",
                "word_canvas",
                "handoff_manifest",
            ],
            "rebuilds": [],
            "steps": [
                {
                    "order": 1,
                    "owner": "礼部 / 刑部",
                    "action": "归档当前 Word、handoff manifest、质量基准和 claim report。",
                    "evidence": "production_quality_verified=true 且 visual_evidence_level=model_reviewed。",
                    "expected": "后续公开展示和下游交接使用同一份证据包。",
                }
            ],
        }

    recovery = benchmark.get("recommended_recovery") or {}
    if claim_level == "needs_review" and recovery:
        return {
            "required": True,
            "reason": str(recovery.get("description") or "当前制片包仍有质量阻塞项，必须先按责任部门修复。"),
            "next_action": "按 recommended_recovery 退回对应阶段，修复阻塞项后重新生成质量基准和 claim report。",
            "recovery_action": str(recovery.get("action") or "review_package"),
            "recovery_endpoint": "/api/workspaces/{workspace_id}/comic/v2/quality/recover",
            "preserves": list(recovery.get("preserves") or []),
            "rebuilds": list(recovery.get("clears") or []),
            "steps": [
                {
                    "order": 1,
                    "owner": str(recovery.get("department") or "责任部门"),
                    "action": str(recovery.get("label") or recovery.get("action") or "按质量问题退回处理"),
                    "evidence": str(recovery.get("reason_code") or "quality_benchmark.issues"),
                    "expected": f"回到 {recovery.get('expected_stage') or 'manual_review'} 阶段。",
                },
                {
                    "order": 2,
                    "owner": "尚书省 / 刑部",
                    "action": "重新运行交付质量基准并确认 blocker_count=0。",
                    "evidence": "quality_benchmark.package_quality_ready=true。",
                    "expected": "制片包从 needs_review 回到可展示或可继续生产状态。",
                },
            ],
        }

    return {
        "required": True,
        "reason": (
            "当前公开样例只证明结构和引用链；"
            f"视觉证据仍是 {visual_level}，不能宣称真实模型画质或人物一致性已验证。"
        ),
        "next_action": "保留已确认故事、资产和提示词包，用真实模型重跑图片、补视觉质检，再重建 Word、handoff manifest 和 claim report。",
        "recovery_action": "regenerate_images",
        "recovery_endpoint": "/api/workspaces/{workspace_id}/comic/v2/quality/recover",
        "preserves": [
            "confirmed_story",
            "asset_manifest",
            "prompt_package",
            "old_word_canvas",
            "old_handoff_manifest",
        ],
        "rebuilds": [
            "image_production_evidence",
            "visual_review",
            "quality_benchmark",
            "word_canvas",
            "handoff_manifest",
            "claim_report",
        ],
        "steps": [
            {
                "order": 1,
                "owner": "使用者",
                "action": "在本地模型页配置并测试文本模型、生图模型和视觉理解模型。",
                "evidence": "模型预检通过；API Key 只留在本机 config.yaml 或本地环境变量。",
                "expected": "真实生产可以开始，公开 demo 仍保持 no-key。",
            },
            {
                "order": 2,
                "owner": "工部 / 刑部",
                "action": "使用已确认故事、资产拆解和提示词包重新生成图片，并执行视觉质检。",
                "evidence": "图片记录包含 provider、model、非 fixture 标记和 review.status=pass。",
                "expected": "image_production_evidence 从 fixture_only 升级为 model_reviewed。",
            },
            {
                "order": 3,
                "owner": "礼部 / 刑部",
                "action": "重新生成 Word 画布、handoff manifest 和 claim report，并保留旧交付物归档。",
                "evidence": "stored_benchmark_matches=true 且 production_quality_verified=true。",
                "expected": "claim_level 才能从 demo_structure_only 升级为 real_quality_verified。",
            },
        ],
    }
