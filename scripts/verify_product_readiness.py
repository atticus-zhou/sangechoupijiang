"""Verify product-level readiness gates for the real local product."""

from __future__ import annotations

import argparse
import json
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.product_readiness import audit_comic_production_readiness, format_readiness_markdown


def run_runtime_verification(root: Path) -> dict:
    """Run deterministic end-to-end verifiers without calling real providers."""
    from scripts.verify_comic_v2_delivery import verify_delivery
    from scripts.verify_comic_v2_user_flow import verify_user_flow

    fixture_path = root / "tests/fixtures/comic_v2_sample.json"
    with TemporaryDirectory(prefix="comic_readiness_") as tmp:
        temp_root = Path(tmp)
        delivery = verify_delivery(fixture_path, temp_root / "delivery")
        user_flow = verify_user_flow(fixture_path, temp_root / "user_flow")

    delivery_passed = bool(delivery.get("handoff_ready"))
    user_flow_passed = (
        user_flow.get("final_stage") == "ready_for_handoff"
        and bool(user_flow.get("delivery_audit", {}).get("handoff_ready"))
        and int(user_flow.get("download_bytes") or 0) > 0
    )
    return {
        "delivery": {
            "status": "passed" if delivery_passed else "failed",
            "handoff_ready": delivery_passed,
            "asset_count": delivery.get("asset_count", 0),
            "shot_count": delivery.get("shot_count", 0),
            "embedded_images": delivery.get("embedded_images", 0),
            "handoff_manifest_exists": bool(delivery.get("handoff_manifest_exists")),
            "handoff_manifest_assets": delivery.get("handoff_manifest_assets", 0),
            "handoff_manifest_images": delivery.get("handoff_manifest_images", 0),
            "handoff_manifest_shots": delivery.get("handoff_manifest_shots", 0),
            "missing_image_asset_ids": delivery.get("missing_image_asset_ids", []),
            "structural_errors": delivery.get("structural_errors", []),
        },
        "user_flow": {
            "status": "passed" if user_flow_passed else "failed",
            "final_stage": user_flow.get("final_stage", ""),
            "visited_stages": user_flow.get("visited_stages", []),
            "generated_images": user_flow.get("generated_images", 0),
            "download_bytes": user_flow.get("download_bytes", 0),
            "artifact_count": user_flow.get("artifact_count", 0),
            "event_count": user_flow.get("event_count", 0),
        },
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format for the readiness audit.",
    )
    parser.add_argument(
        "--run-e2e",
        action="store_true",
        help="Run deterministic delivery and user-flow verifiers.",
    )
    args = parser.parse_args()

    audit = audit_comic_production_readiness(REPO_ROOT)
    if args.run_e2e:
        audit["runtime_verification"] = run_runtime_verification(REPO_ROOT)
        runtime_failed = any(
            item.get("status") != "passed"
            for item in audit["runtime_verification"].values()
        )
        if runtime_failed:
            audit["status"] = "needs_work"
            audit["summary"] = "AI 漫剧制片办公室静态条件存在，但运行时验证未全部通过。"
    if args.format == "markdown":
        print(format_readiness_markdown(audit))
    else:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit.get("status") == "ready_without_demo" else 1


if __name__ == "__main__":
    raise SystemExit(main())
