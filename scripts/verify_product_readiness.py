"""Verify product-level readiness gates for the real local product."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.product_readiness import audit_comic_production_readiness, format_readiness_markdown


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
    args = parser.parse_args()

    audit = audit_comic_production_readiness(REPO_ROOT)
    if args.format == "markdown":
        print(format_readiness_markdown(audit))
    else:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit.get("status") == "ready_without_demo" else 1


if __name__ == "__main__":
    raise SystemExit(main())
