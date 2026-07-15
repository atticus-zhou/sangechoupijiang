"""Verify AI comic handoff quality across story, assets, prompts, shots, and reviews."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_comic_v2_delivery import verify_delivery
from src.comic_office.v2.production_benchmark import audit_handoff_manifest


DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "comic_v2_sample.json"
DEFAULT_OUTPUT = REPO_ROOT / "output" / "comic_v2_production_benchmark"


def verify_production_benchmark(
    fixture: Path = DEFAULT_FIXTURE,
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Audit a supplied real handoff or generate the deterministic sample first."""
    delivery: dict[str, Any] | None = None
    if manifest_path is None:
        delivery = verify_delivery(Path(fixture), Path(output_dir))
        manifest_path = Path(str(delivery["handoff_manifest_path"]))
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    audit = audit_handoff_manifest(manifest)
    stored = manifest.get("quality_benchmark") or {}
    stored_matches = all(
        stored.get(field) == audit.get(field)
        for field in (
            "benchmark_version",
            "status",
            "package_quality_score",
            "package_quality_ready",
            "production_quality_verified",
            "visual_evidence_level",
            "issue_count",
            "blocker_count",
            "recommended_recovery",
        )
    )
    passed = bool(audit.get("package_quality_ready")) and stored_matches
    return {
        **audit,
        "quality_claim": audit.get("status", ""),
        "status": "passed" if passed else "failed",
        "mode": "comic_production_quality_benchmark",
        "manifest_path": str(path),
        "word_canvas": (delivery or {}).get("path") or (manifest.get("word_canvas") or {}).get("relative_path", ""),
        "manifest_schema": manifest.get("schema", ""),
        "manifest_schema_version": manifest.get("schema_version", 0),
        "stored_benchmark_matches": stored_matches,
    }


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# AI Comic Production Quality Benchmark",
        "",
        f"Status: `{result.get('status')}`",
        f"Quality claim: `{result.get('quality_claim')}`",
        f"Package quality score: `{result.get('package_quality_score')}/100`",
        f"Package quality ready: `{result.get('package_quality_ready')}`",
        f"Production quality verified: `{result.get('production_quality_verified')}`",
        f"Visual evidence: `{result.get('visual_evidence_level')}`",
        f"Manifest: `{result.get('manifest_path')}`",
        f"Stored benchmark matches: `{result.get('stored_benchmark_matches')}`",
        "",
        "## Quality Dimensions",
        "",
        "| Dimension | Status | Score |",
        "| --- | --- | ---: |",
    ]
    for dimension in result.get("dimensions", []):
        lines.append(
            f"| {dimension.get('label')} | {dimension.get('status')} | {dimension.get('score')}/100 |"
        )
    if result.get("issues"):
        lines.extend(["", "## Issues", ""])
        for issue in result["issues"]:
            lines.append(
                f"- [{issue.get('severity')}] {issue.get('department') or '待分配'} · "
                f"{issue.get('dimension')}/{issue.get('code')}: "
                f"{issue.get('message')} ({issue.get('evidence')})"
            )
    if result.get("limitations"):
        lines.extend(["", "## Honest Limitations", ""])
        lines.extend(f"- {item}" for item in result["limitations"])
    recovery = result.get("recommended_recovery") or {}
    lines.extend(["", "## Next Action", ""])
    if recovery:
        lines.append(
            f"- 责任部门：{recovery.get('department') or '待分配'}"
        )
        lines.append(
            f"- 恢复动作：{recovery.get('label') or recovery.get('action') or '人工复核'}"
        )
        if recovery.get("expected_stage"):
            lines.append(f"- 回到阶段：`{recovery.get('expected_stage')}`")
        if recovery.get("preserves"):
            lines.append(f"- 保留产物：{', '.join(recovery.get('preserves') or [])}")
        if recovery.get("clears"):
            lines.append(f"- 重新生成：{', '.join(recovery.get('clears') or [])}")
        for step in recovery.get("operator_steps") or []:
            lines.append(f"- 操作步骤：{step}")
    lines.append(str(result.get("next_action") or ""))
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Audit an AI comic production handoff.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="markdown")
    args = parser.parse_args()

    result = verify_production_benchmark(
        args.fixture,
        args.output_dir,
        manifest_path=args.manifest,
    )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(format_markdown(result))
    else:
        print(
            "AI comic production benchmark: "
            f"{result['status']} ({result.get('package_quality_score')}/100, "
            f"{result.get('visual_evidence_level')})"
        )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
