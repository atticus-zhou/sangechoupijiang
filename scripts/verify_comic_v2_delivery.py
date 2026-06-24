"""Build and verify the deterministic comic-production V2 sample."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from docx import Document

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.comic_office.v2.asset_manifest import build_asset_manifest
from src.comic_office.v2.contracts import build_contract_bundle
from src.comic_office.v2.prompt_director import build_shot_card
from src.comic_office.v2.word_canvas import build_word_canvas_v2


PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZrWQAAAAASUVORK5CYII="
)


def verify_delivery(fixture_path: Path, output_dir: Path) -> dict:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    bundle = build_contract_bundle(fixture["source_story"], fixture["planner_payload"])
    manifest = build_asset_manifest(bundle, fixture["assets"])
    assets_by_name = {item.name: item for item in manifest.items}
    shots = []
    for payload in fixture["shots"]:
        shots.append(build_shot_card(
            payload,
            characters=[assets_by_name[name] for name in payload["characters"]],
            props=[assets_by_name[name] for name in payload["props"]],
            scene=assets_by_name[payload["scene"]],
            visual=bundle.visual,
        ))

    image_dir = output_dir / "fixture-images"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_paths = {}
    for asset in manifest.items:
        image_path = image_dir / f"{asset.asset_id}.png"
        image_path.write_bytes(PLACEHOLDER_PNG)
        image_paths[asset.asset_id] = str(image_path)

    build = build_word_canvas_v2(bundle, manifest, tuple(shots), image_paths, output_dir)
    doc = Document(build.path)
    text = "\n".join(
        [paragraph.text for paragraph in doc.paragraphs]
        + [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    )
    missing_ids = [
        identifier
        for identifier in [*(item.asset_id for item in manifest.items), *(shot.shot_id for shot in shots)]
        if identifier not in text
    ]
    if missing_ids:
        raise AssertionError(f"delivery is missing IDs: {', '.join(missing_ids)}")
    audit = build.audit
    result = {
        "path": str(build.path),
        "handoff_ready": audit.handoff_ready,
        "asset_count": audit.asset_count,
        "shot_count": audit.shot_count,
        "embedded_images": audit.embedded_images,
        "max_table_columns": audit.max_table_columns,
        "missing_image_asset_ids": list(audit.missing_image_asset_ids),
        "structural_errors": list(audit.structural_errors),
    }
    if not result["handoff_ready"]:
        raise AssertionError(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/comic_v2_sample.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/comic_v2_verification"),
    )
    args = parser.parse_args()
    result = verify_delivery(args.fixture, args.output_dir)
    print(f"V2 delivery verified: {result['path']}")


if __name__ == "__main__":
    main()
