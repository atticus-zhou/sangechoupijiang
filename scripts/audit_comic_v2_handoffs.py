"""Inventory and audit AI comic V2 handoff manifests.

This script is intentionally no-key. It does not call models; it only reads
handoff manifests that were already generated and classifies whether they are
production verified, demo-only, recoverable, or legacy/unverifiable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.comic_office.v2.production_benchmark import audit_handoff_manifest


DEFAULT_ROOTS = (REPO_ROOT / "output",)


def audit_handoff_inventory(roots: list[Path] | None = None) -> dict[str, Any]:
    scan_roots = [Path(root) for root in (roots or list(DEFAULT_ROOTS))]
    manifests = []
    skipped = []
    for root in scan_roots:
        if not root.exists():
            skipped.append({"root": str(root), "reason": "missing"})
            continue
        for path in _candidate_manifest_paths(root):
            item = _audit_manifest_path(path)
            if item:
                manifests.append(item)

    manifests.sort(key=lambda item: (item.get("updated_at") or "", item["path"]), reverse=True)
    by_claim: dict[str, int] = {}
    for item in manifests:
        by_claim[item["quality_claim"]] = by_claim.get(item["quality_claim"], 0) + 1

    production_verified = [item for item in manifests if item["quality_claim"] == "production_quality_verified"]
    demo_only = [item for item in manifests if item["quality_claim"] == "demo_structure_verified"]
    needs_review = [item for item in manifests if item["quality_claim"] == "needs_review"]
    legacy = [item for item in manifests if item["quality_claim"] == "legacy_unverifiable"]
    return {
        "status": "passed" if manifests else "warning",
        "mode": "comic_v2_handoff_inventory",
        "root_count": len(scan_roots),
        "manifest_count": len(manifests),
        "production_verified_count": len(production_verified),
        "demo_only_count": len(demo_only),
        "needs_review_count": len(needs_review),
        "legacy_unverifiable_count": len(legacy),
        "quality_claim_counts": by_claim,
        "safe_public_claim": (
            "真实模型质量已验证" if production_verified else "暂无真实模型质量通过证据；只能展示结构样例或历史交付"
        ),
        "next_action": _inventory_next_action(production_verified, demo_only, needs_review, legacy),
        "manifests": manifests,
        "skipped_roots": skipped,
    }


def _candidate_manifest_paths(root: Path) -> list[Path]:
    patterns = ("*handoff_manifest*.json", "*v2_handoff*.json")
    paths: set[Path] = set()
    for pattern in patterns:
        try:
            paths.update(root.rglob(pattern))
        except OSError:
            continue
    return sorted(path for path in paths if path.is_file())


def _audit_manifest_path(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not _looks_like_comic_v2_handoff(payload):
        return None

    benchmark = audit_handoff_manifest(payload)
    stored = payload.get("quality_benchmark") or {}
    stored_status = str(stored.get("status") or "")
    claim = str(benchmark.get("status") or "needs_review")
    schema_version = int(payload.get("schema_version") or 0)
    if schema_version < 3 and not stored_status:
        claim = "legacy_unverifiable"
    word_canvas = payload.get("word_canvas") or {}
    word_path = _resolve_word_path(path, word_canvas)
    recovery = benchmark.get("recommended_recovery") or {}
    if not recovery:
        if claim == "demo_structure_verified":
            recovery = _demo_only_recovery()
        elif claim == "legacy_unverifiable":
            recovery = _legacy_recovery()
    return {
        "path": str(path),
        "title": ((payload.get("story") or {}).get("title") or path.stem),
        "schema": payload.get("schema") or "",
        "schema_version": schema_version,
        "quality_claim": claim,
        "package_quality_score": int(benchmark.get("package_quality_score") or 0),
        "production_quality_verified": bool(benchmark.get("production_quality_verified")),
        "visual_evidence_level": benchmark.get("visual_evidence_level") or "",
        "issue_count": int(benchmark.get("issue_count") or 0),
        "blocker_count": int(benchmark.get("blocker_count") or 0),
        "recommended_recovery": recovery,
        "next_action": _manifest_next_action(claim, benchmark, recovery),
        "word_canvas_path": str(word_path) if word_path else "",
        "word_canvas_exists": bool(word_path and word_path.exists()),
        "asset_count": len(payload.get("assets") or []),
        "image_count": len(payload.get("images") or []),
        "shot_count": len(payload.get("shots") or []),
        "updated_at": _updated_at(path),
    }


def _looks_like_comic_v2_handoff(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    schema = str(payload.get("schema") or "")
    if schema in {"comic_v2_handoff_manifest", "comic_v2_delivery_manifest"}:
        return True
    return all(key in payload for key in ("story", "assets", "images", "shots", "word_canvas"))


def _resolve_word_path(manifest_path: Path, word_canvas: dict[str, Any]) -> Path | None:
    filename = word_canvas.get("filename") or word_canvas.get("relative_path")
    if not filename:
        return None
    candidate = Path(str(filename))
    if candidate.is_absolute():
        return candidate
    same_dir = manifest_path.parent / candidate.name
    if same_dir.exists():
        return same_dir
    return manifest_path.parent / candidate


def _updated_at(path: Path) -> str:
    try:
        return path.stat().st_mtime_ns.__str__()
    except OSError:
        return ""


def _manifest_next_action(claim: str, benchmark: dict[str, Any], recovery: dict[str, Any]) -> str:
    if claim == "production_quality_verified":
        return "可以作为真实模型制片包交给下游图生视频或剪辑流程。"
    if claim == "demo_structure_verified":
        return str(
            recovery.get("description")
            or "只适合公开演示结构；真实创作后请补跑真实图片生成和视觉质检。"
        )
    if claim == "legacy_unverifiable":
        return str(
            recovery.get("description")
            or "旧版包缺少 V3 质量清单；建议重新生成或补齐 V3 引用与质量基准。"
        )
    return str(
        recovery.get("description")
        or benchmark.get("next_action")
        or "先处理质量基准中的阻塞项。"
    )


def _inventory_next_action(
    production_verified: list[dict[str, Any]],
    demo_only: list[dict[str, Any]],
    needs_review: list[dict[str, Any]],
    legacy: list[dict[str, Any]],
) -> str:
    if production_verified:
        return "已有真实质量通过的制片包，可优先展示最近一份并保留审计清单。"
    if needs_review:
        return "先按责任部门处理 needs_review 制片包，再重新生成 Word 和 handoff manifest。"
    if demo_only:
        return "当前只有无 Key 结构样例；公开展示可以用，但不能宣称真实画质已验证。下一步应保留故事、资产和提示词，补跑真实图片生成与视觉质检。"
    if legacy:
        return "当前只有旧版不可审计包；请用 V2/V3 流程重新生产一份可追溯制片包。"
    return "没有找到可审计的 AI 漫剧 V2 handoff manifest。"


def _demo_only_recovery() -> dict[str, Any]:
    return {
        "action": "regenerate_images",
        "label": "补跑真实图片与视觉质检",
        "department": "工部 / 刑部",
        "expected_stage": "image_generation",
        "description": "这份包是无 Key 结构样例，不能证明真实画质。保留已确认故事、资产清单和提示词包，清掉 fixture 图片证据后补跑真实生图和七维视觉质检。",
        "preserves": ["story_contract", "asset_manifest", "prompt_package", "word_canvas_archive"],
        "clears": ["fixture_images", "image_reviews", "real_quality_claim"],
        "operator_steps": [
            "确认工部已配置生图模型，刑部已配置视觉理解模型。",
            "从历史页或恢复接口执行 regenerate_images，保留当前故事、资产和提示词版本。",
            "重新运行质量基准；只有 production_quality_verified 通过后，才宣称真实画质已验证。",
        ],
    }


def _legacy_recovery() -> dict[str, Any]:
    return {
        "action": "rebuild_v3_handoff",
        "label": "重建 V3 制片包",
        "department": "礼部 / 刑部",
        "expected_stage": "delivery_packaging",
        "description": "旧版包缺少 V3 handoff manifest 或质量基准，不能证明故事、资产、图片和 Word 来自同一版本。请重新组装 V3 交付物。",
        "preserves": ["word_canvas_archive", "available_images"],
        "clears": ["legacy_quality_claim"],
        "operator_steps": [
            "保留旧 Word 作为历史归档，不把它当作质量通过证据。",
            "重新生成 V3 handoff manifest、production_lineage 和 quality_benchmark。",
            "补齐后重新运行 handoff inventory 和 production benchmark。",
        ],
    }


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# AI Comic V2 Handoff Inventory",
        "",
        f"Status: `{result.get('status')}`",
        f"Manifests: `{result.get('manifest_count')}`",
        f"Production verified: `{result.get('production_verified_count')}`",
        f"Demo only: `{result.get('demo_only_count')}`",
        f"Needs review: `{result.get('needs_review_count')}`",
        f"Legacy unverifiable: `{result.get('legacy_unverifiable_count')}`",
        f"Public claim: {result.get('safe_public_claim')}",
        f"Next action: {result.get('next_action')}",
        "",
        "| Claim | Score | Visual evidence | Title | Word | Recovery | Stage | Impact | Manifest |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in result.get("manifests", []):
        recovery = item.get("recommended_recovery") or {}
        lines.append(
            f"| {item.get('quality_claim')} | {item.get('package_quality_score')}/100 | "
            f"{item.get('visual_evidence_level')} | {item.get('title')} | "
            f"{'yes' if item.get('word_canvas_exists') else 'missing'} | "
            f"{recovery.get('label') or recovery.get('action') or ''} | "
            f"{recovery.get('expected_stage') or ''} | "
            f"preserve={','.join(recovery.get('preserves') or [])}; clear={','.join(recovery.get('clears') or [])} | "
            f"`{item.get('path')}` |"
        )
    if result.get("skipped_roots"):
        lines.extend(["", "## Skipped Roots", ""])
        for item in result["skipped_roots"]:
            lines.append(f"- `{item.get('root')}`: {item.get('reason')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Inventory AI comic V2 handoff manifests.")
    parser.add_argument("--root", action="append", type=Path, help="Directory to scan. Can be supplied more than once.")
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="markdown")
    args = parser.parse_args()

    result = audit_handoff_inventory(args.root)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(format_markdown(result))
    else:
        print(
            "AI comic handoff inventory: "
            f"{result['status']} ({result.get('manifest_count')} manifests, "
            f"{result.get('production_verified_count')} production verified)"
        )
    return 0 if result["manifest_count"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
