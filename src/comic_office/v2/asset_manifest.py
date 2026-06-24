"""Evidence-backed asset manifests for comic production V2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import ContractBundle, story_hash


class ManifestValidationError(ValueError):
    """Raised when an asset cannot be traced to the confirmed story."""


class NoManifestChangeError(ManifestValidationError):
    """Raised when a requested revision produces the same asset inventory."""


_ASSET_TYPES = {"character", "prop", "scene"}
_DEFAULT_IMAGES = {
    "character": ("three_view", "expression_sheet"),
    "prop": ("turnaround", "state_sheet"),
    "scene": ("wide", "top_down", "camera_angles"),
}


@dataclass(frozen=True)
class AssetEvidence:
    evidence_quote: str
    scene_ids: tuple[str, ...]


@dataclass(frozen=True)
class AssetPlan:
    asset_id: str
    asset_type: str
    name: str
    evidence: AssetEvidence
    story_purpose: str
    visual_locks: tuple[str, ...]
    allowed_changes: tuple[str, ...]
    planned_images: tuple[str, ...]
    review_status: str = "awaiting_user_review"


@dataclass(frozen=True)
class AssetManifest:
    manifest_id: str
    manifest_hash: str
    version: int
    story_id: str
    story_version: int
    style_id: str
    style_version: int
    source_hash: str
    items: tuple[AssetPlan, ...]
    review_status: str = "awaiting_user_review"
    revision_note: str = ""
    source_story: str = field(default="", repr=False)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("source_story", None)
        return payload


def build_asset_manifest(
    bundle: ContractBundle,
    assets: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    version: int = 1,
    revision_note: str = "",
) -> AssetManifest:
    """Build a formal manifest whose every item cites the confirmed story."""
    if story_hash(bundle.creative.source_story) != bundle.creative.source_hash:
        raise ManifestValidationError("confirmed story no longer matches its contract")
    if not isinstance(assets, (list, tuple)) or not assets:
        raise ManifestValidationError("asset inventory is empty")
    items = tuple(_asset_plan(bundle, payload) for payload in assets)
    _reject_duplicate_assets(items)
    content_hash = _manifest_content_hash(
        bundle.creative.story_id,
        bundle.creative.story_version,
        bundle.visual.style_id,
        bundle.visual.style_version,
        items,
    )
    return AssetManifest(
        manifest_id=f"manifest_{bundle.creative.story_id.removeprefix('story_')}",
        manifest_hash=content_hash,
        version=_positive_version(version),
        story_id=bundle.creative.story_id,
        story_version=bundle.creative.story_version,
        style_id=bundle.visual.style_id,
        style_version=bundle.visual.style_version,
        source_hash=bundle.creative.source_hash,
        source_story=bundle.creative.source_story,
        items=items,
        revision_note=(revision_note or "").strip(),
    )


def revise_asset_manifest(
    previous: AssetManifest,
    user_note: str,
    proposed_assets: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> AssetManifest:
    """Merge a user's requested changes into a new, meaningfully different version."""
    note = (user_note or "").strip()
    if not note:
        raise ManifestValidationError("revision note is required")
    if not isinstance(proposed_assets, (list, tuple)) or not proposed_assets:
        raise ManifestValidationError("revision did not provide any assets")
    proposed = tuple(_asset_plan_from_manifest(previous, payload) for payload in proposed_assets)
    _reject_duplicate_assets(proposed)

    merged: dict[tuple[str, str], AssetPlan] = {
        (item.asset_type, item.name): item for item in previous.items
    }
    for item in proposed:
        merged[(item.asset_type, item.name)] = item
    merged_items = tuple(merged.values())
    content_hash = _manifest_content_hash(
        previous.story_id,
        previous.story_version,
        previous.style_id,
        previous.style_version,
        merged_items,
    )
    if content_hash == previous.manifest_hash:
        raise NoManifestChangeError("revision produced no asset changes")
    return AssetManifest(
        manifest_id=previous.manifest_id,
        manifest_hash=content_hash,
        version=previous.version + 1,
        story_id=previous.story_id,
        story_version=previous.story_version,
        style_id=previous.style_id,
        style_version=previous.style_version,
        source_hash=previous.source_hash,
        source_story=previous.source_story,
        items=merged_items,
        review_status="awaiting_user_review",
        revision_note=note,
    )


def replace_asset_manifest(
    previous: AssetManifest,
    user_note: str,
    proposed_assets: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> AssetManifest:
    """Replace the full inventory so a revision can both add and remove assets."""
    note = (user_note or "").strip()
    if not note:
        raise ManifestValidationError("revision note is required")
    if not isinstance(proposed_assets, (list, tuple)) or not proposed_assets:
        raise ManifestValidationError("revision did not provide a full asset inventory")
    items = tuple(_asset_plan_from_manifest(previous, payload) for payload in proposed_assets)
    _reject_duplicate_assets(items)
    content_hash = _manifest_content_hash(
        previous.story_id,
        previous.story_version,
        previous.style_id,
        previous.style_version,
        items,
    )
    if content_hash == previous.manifest_hash:
        raise NoManifestChangeError("revision produced no asset changes")
    return AssetManifest(
        manifest_id=previous.manifest_id,
        manifest_hash=content_hash,
        version=previous.version + 1,
        story_id=previous.story_id,
        story_version=previous.story_version,
        style_id=previous.style_id,
        style_version=previous.style_version,
        source_hash=previous.source_hash,
        source_story=previous.source_story,
        items=items,
        review_status="awaiting_user_review",
        revision_note=note,
    )


def asset_manifest_from_dict(payload: dict[str, Any], *, source_story: str) -> AssetManifest:
    """Restore a persisted manifest while rechecking its source-story binding."""
    if not isinstance(payload, dict):
        raise ManifestValidationError("manifest payload must be an object")
    if story_hash(source_story) != str(payload.get("source_hash") or ""):
        raise ManifestValidationError("manifest source story hash does not match")
    items = []
    for raw in payload.get("items") or []:
        evidence = raw.get("evidence") or {}
        items.append(AssetPlan(
            asset_id=str(raw.get("asset_id") or ""),
            asset_type=str(raw.get("asset_type") or ""),
            name=str(raw.get("name") or ""),
            evidence=AssetEvidence(
                evidence_quote=str(evidence.get("evidence_quote") or ""),
                scene_ids=tuple(evidence.get("scene_ids") or ()),
            ),
            story_purpose=str(raw.get("story_purpose") or ""),
            visual_locks=tuple(raw.get("visual_locks") or ()),
            allowed_changes=tuple(raw.get("allowed_changes") or ()),
            planned_images=tuple(raw.get("planned_images") or ()),
            review_status=str(raw.get("review_status") or "awaiting_user_review"),
        ))
    restored = AssetManifest(
        manifest_id=str(payload.get("manifest_id") or ""),
        manifest_hash=str(payload.get("manifest_hash") or ""),
        version=_positive_version(payload.get("version")),
        story_id=str(payload.get("story_id") or ""),
        story_version=_positive_version(payload.get("story_version")),
        style_id=str(payload.get("style_id") or ""),
        style_version=_positive_version(payload.get("style_version")),
        source_hash=str(payload.get("source_hash") or ""),
        source_story=source_story,
        items=tuple(items),
        review_status=str(payload.get("review_status") or "awaiting_user_review"),
        revision_note=str(payload.get("revision_note") or ""),
    )
    expected_hash = _manifest_content_hash(
        restored.story_id,
        restored.story_version,
        restored.style_id,
        restored.style_version,
        restored.items,
    )
    if expected_hash != restored.manifest_hash:
        raise ManifestValidationError("manifest content hash does not match")
    return restored


def _asset_plan(bundle: ContractBundle, payload: dict[str, Any]) -> AssetPlan:
    return _normalize_asset_plan(
        story_id=bundle.creative.story_id,
        source_story=bundle.creative.source_story,
        payload=payload,
    )


def _asset_plan_from_manifest(previous: AssetManifest, payload: dict[str, Any]) -> AssetPlan:
    return _normalize_asset_plan(
        story_id=previous.story_id,
        source_story=previous.source_story,
        payload=payload,
    )


def _normalize_asset_plan(story_id: str, source_story: str, payload: dict[str, Any]) -> AssetPlan:
    if not isinstance(payload, dict):
        raise ManifestValidationError("asset must be an object")
    required = ("asset_type", "name", "evidence_quote", "scene_ids", "story_purpose", "visual_locks", "allowed_changes")
    missing = [field for field in required if not _has_value(payload.get(field))]
    if missing:
        raise ManifestValidationError(f"asset missing fields: {', '.join(missing)}")
    asset_type = str(payload["asset_type"]).strip().lower()
    if asset_type not in _ASSET_TYPES:
        raise ManifestValidationError(f"unsupported asset type: {asset_type}")
    name = str(payload["name"]).strip()
    evidence_quote = str(payload["evidence_quote"]).strip()
    if evidence_quote not in source_story:
        raise ManifestValidationError(f"asset evidence is not present in story: {name}")
    key = f"{story_id}:{asset_type}:{name}".encode("utf-8")
    asset_digest = hashlib.sha256(key).hexdigest()[:10]
    planned_images = payload.get("planned_images") or _DEFAULT_IMAGES[asset_type]
    return AssetPlan(
        asset_id=f"{asset_type}_{asset_digest}",
        asset_type=asset_type,
        name=name,
        evidence=AssetEvidence(
            evidence_quote=evidence_quote,
            scene_ids=_string_tuple(payload["scene_ids"], "scene_ids"),
        ),
        story_purpose=str(payload["story_purpose"]).strip(),
        visual_locks=_string_tuple(payload["visual_locks"], "visual_locks"),
        allowed_changes=_string_tuple(payload["allowed_changes"], "allowed_changes"),
        planned_images=_string_tuple(planned_images, "planned_images"),
    )


def _manifest_content_hash(
    story_id: str,
    story_version: int,
    style_id: str,
    style_version: int,
    items: tuple[AssetPlan, ...],
) -> str:
    normalized = {
        "story_id": story_id,
        "story_version": story_version,
        "style_id": style_id,
        "style_version": style_version,
        "items": [asdict(item) for item in sorted(items, key=lambda item: (item.asset_type, item.name))],
    }
    raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _reject_duplicate_assets(items: tuple[AssetPlan, ...]) -> None:
    keys = [(item.asset_type, item.name) for item in items]
    if len(keys) != len(set(keys)):
        raise ManifestValidationError("asset inventory contains duplicate type/name pairs")


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ManifestValidationError(f"{label} must be an array")
    result = tuple(str(item).strip() for item in value if str(item).strip())
    if not result:
        raise ManifestValidationError(f"{label} must contain at least one item")
    return result


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _positive_version(value: Any) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise ManifestValidationError("manifest version must be an integer") from exc
    if version < 1:
        raise ManifestValidationError("manifest version must be positive")
    return version
