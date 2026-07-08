"""Schema registry for model outputs in the comic-production V2 pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import (
    ContractBundle,
    ContractValidationError,
    build_contract_bundle,
)
from .asset_manifest import (
    AssetManifest,
    AssetPlan,
    ManifestValidationError,
    NoManifestChangeError,
    build_asset_manifest,
    replace_asset_manifest,
)
from .prompt_director import (
    PromptPlan,
    ShotCard,
    build_shot_card,
    parse_prompt_director_response,
)
from .visual_review import (
    VisualReviewRequest,
    VisualReviewResult,
    normalize_baseline_review,
    normalize_visual_review,
)


class AgentOutputSchemaError(ValueError):
    """Raised when an agent output does not satisfy its declared schema gate."""


@dataclass(frozen=True)
class AgentOutputSchema:
    office_id: str
    schema_id: str
    owner_agent: str
    stage: str
    description: str
    required_fields: tuple[str, ...]
    failure_impact: str
    validator: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_fields"] = list(self.required_fields)
        return payload


_SCHEMAS: dict[tuple[str, str], AgentOutputSchema] = {
    ("comic_production", "comic_contract"): AgentOutputSchema(
        office_id="comic_production",
        schema_id="comic_contract",
        owner_agent="zhongshu",
        stage="story_contract",
        description="Confirmed story to formal creative contract and visual bible.",
        required_fields=(
            "title",
            "genre",
            "theme",
            "protagonist_goal",
            "main_conflict",
            "causal_chain",
            "ending",
            "episodes",
            "visual",
        ),
        failure_impact="The production chain cannot enter visual bible review or asset planning.",
        validator="_validate_comic_contract",
    ),
    ("comic_production", "visual_revision"): AgentOutputSchema(
        office_id="comic_production",
        schema_id="visual_revision",
        owner_agent="zhongshu",
        stage="visual_bible_review",
        description="Human revision request to a new visual bible version.",
        required_fields=("visual",),
        failure_impact="The visual bible cannot be approved, so asset prompts would inherit an invalid style.",
        validator="_validate_visual_revision",
    ),
    ("comic_production", "asset_manifest"): AgentOutputSchema(
        office_id="comic_production",
        schema_id="asset_manifest",
        owner_agent="zhongshu",
        stage="asset_review",
        description="Model asset inventory to evidence-backed character, prop, and scene manifest.",
        required_fields=("assets",),
        failure_impact="The user cannot review assets and downstream image prompts would lose story evidence.",
        validator="_validate_asset_manifest",
    ),
    ("comic_production", "asset_manifest_revision"): AgentOutputSchema(
        office_id="comic_production",
        schema_id="asset_manifest_revision",
        owner_agent="zhongshu",
        stage="asset_review",
        description="Human revision request to a replacement asset manifest with version lineage.",
        required_fields=("assets",),
        failure_impact="Returned asset feedback cannot be trusted or traced to a new manifest version.",
        validator="_validate_asset_manifest_revision",
    ),
    ("comic_production", "asset_prompt_set"): AgentOutputSchema(
        office_id="comic_production",
        schema_id="asset_prompt_set",
        owner_agent="gongbu",
        stage="prompt_package",
        description="Model prompt JSON for all planned images of one approved asset.",
        required_fields=("prompts",),
        failure_impact="The image generator would receive incomplete or unbound asset prompts.",
        validator="_validate_asset_prompt_set",
    ),
    ("comic_production", "shot_cards"): AgentOutputSchema(
        office_id="comic_production",
        schema_id="shot_cards",
        owner_agent="bingbu",
        stage="shot_package",
        description="Model shot/video prompt cards bound to approved asset identities.",
        required_fields=("shots",),
        failure_impact="The Word canvas and downstream video tools would lose shot-to-asset traceability.",
        validator="_validate_shot_cards",
    ),
    ("comic_production", "image_review_result"): AgentOutputSchema(
        office_id="comic_production",
        schema_id="image_review_result",
        owner_agent="xingbu",
        stage="image_quality_review",
        description="Vision QA output normalized to a formal image consistency review.",
        required_fields=("status", "scores"),
        failure_impact="Bad or incomplete image QA could promote inconsistent assets into the final canvas.",
        validator="_validate_image_review_result",
    ),
}


def list_agent_output_schemas(office_id: str | None = None) -> list[dict[str, Any]]:
    """Return declared schema gates, optionally scoped to one office."""
    normalized = str(office_id or "").strip()
    schemas = [
        schema
        for (candidate_office, _), schema in sorted(_SCHEMAS.items())
        if not normalized or candidate_office == normalized
    ]
    return [schema.to_dict() for schema in schemas]


def validate_agent_output_schema(
    office_id: str,
    schema_id: str,
    payload: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> ContractBundle | AssetManifest | tuple[PromptPlan, ...] | tuple[ShotCard, ...] | VisualReviewResult:
    """Validate a model output against a named office schema gate."""
    key = (str(office_id or "").strip(), str(schema_id or "").strip())
    schema = _SCHEMAS.get(key)
    if schema is None:
        raise AgentOutputSchemaError(f"unknown agent output schema: {key[0]}/{key[1]}")
    if not isinstance(payload, dict):
        raise AgentOutputSchemaError(f"{schema.schema_id} output must be an object")
    missing = [field for field in schema.required_fields if not _has_value(payload.get(field))]
    if missing:
        raise AgentOutputSchemaError(f"{schema.schema_id} missing fields: {', '.join(missing)}")
    validator = _VALIDATORS[schema.validator]
    return validator(payload, context or {})


def _validate_comic_contract(payload: dict[str, Any], context: dict[str, Any]) -> ContractBundle:
    source_story = str(context.get("source_story") or "")
    try:
        return build_contract_bundle(
            source_story,
            payload,
            source_mode=str(context.get("source_mode") or "full_story"),
            story_version=int(context.get("story_version") or 1),
            style_version=int(context.get("style_version") or 1),
        )
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise AgentOutputSchemaError(f"comic_contract failed schema validation: {exc}") from exc


def _validate_visual_revision(payload: dict[str, Any], context: dict[str, Any]) -> ContractBundle:
    current_contract = context.get("current_contract") or {}
    creative = current_contract.get("creative") or {}
    current_visual = current_contract.get("visual") or {}
    if not isinstance(creative, dict) or not isinstance(current_visual, dict):
        raise AgentOutputSchemaError("visual_revision requires current creative contract and visual bible")
    planner_payload = {
        "title": creative.get("title", ""),
        "genre": creative.get("genre", ""),
        "theme": creative.get("theme", ""),
        "protagonist_goal": creative.get("protagonist_goal", ""),
        "main_conflict": creative.get("main_conflict", ""),
        "causal_chain": list(creative.get("causal_chain") or []),
        "ending": creative.get("ending", ""),
        "episodes": [
            {
                "episode": item.get("episode"),
                "summary": item.get("summary", ""),
                "evidence_quote": item.get("evidence_quote", ""),
            }
            for item in (creative.get("episodes") or [])
        ],
        "must_keep": list(creative.get("must_keep") or []),
        "must_avoid": list(creative.get("must_avoid") or []),
        "visual": payload["visual"],
    }
    try:
        return build_contract_bundle(
            str(creative.get("source_story") or ""),
            planner_payload,
            source_mode=str(creative.get("source_mode") or "full_story"),
            story_version=int(creative.get("story_version") or 1),
            style_version=int(current_visual.get("style_version") or 1) + 1,
        )
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise AgentOutputSchemaError(f"visual_revision failed schema validation: {exc}") from exc


def _validate_asset_manifest(payload: dict[str, Any], context: dict[str, Any]) -> AssetManifest:
    bundle = context.get("contract_bundle")
    if not isinstance(bundle, ContractBundle):
        raise AgentOutputSchemaError("asset_manifest requires a formal contract bundle")
    try:
        return build_asset_manifest(bundle, payload["assets"])
    except (ManifestValidationError, TypeError, ValueError) as exc:
        raise AgentOutputSchemaError(f"asset_manifest failed schema validation: {exc}") from exc


def _validate_asset_manifest_revision(payload: dict[str, Any], context: dict[str, Any]) -> AssetManifest:
    previous = context.get("previous_manifest")
    if not isinstance(previous, AssetManifest):
        raise AgentOutputSchemaError("asset_manifest_revision requires the previous asset manifest")
    revision_request = str(context.get("revision_request") or "").strip()
    if not revision_request:
        raise AgentOutputSchemaError("asset_manifest_revision requires a revision request")
    try:
        return replace_asset_manifest(previous, revision_request, payload["assets"])
    except NoManifestChangeError as exc:
        raise AgentOutputSchemaError("退回重拆没有产生变化") from exc
    except (ManifestValidationError, TypeError, ValueError) as exc:
        raise AgentOutputSchemaError(f"asset_manifest_revision failed schema validation: {exc}") from exc


def _validate_asset_prompt_set(payload: dict[str, Any], context: dict[str, Any]) -> tuple[PromptPlan, ...]:
    asset = context.get("asset")
    visual = context.get("visual")
    if not isinstance(asset, AssetPlan):
        raise AgentOutputSchemaError("asset_prompt_set requires the current asset plan")
    if visual is None:
        raise AgentOutputSchemaError("asset_prompt_set requires the active visual bible")
    result = parse_prompt_director_response(json.dumps(payload, ensure_ascii=False))
    if not result.production_ready:
        raise AgentOutputSchemaError(f"asset_prompt_set failed schema validation: {result.error}")
    try:
        _validate_prompt_set_binding(asset, visual, result.prompts)
    except ValueError as exc:
        raise AgentOutputSchemaError(f"asset_prompt_set failed schema validation: {exc}") from exc
    return _ordered_prompts(asset, result.prompts)


def _validate_shot_cards(payload: dict[str, Any], context: dict[str, Any]) -> tuple[ShotCard, ...]:
    bundle = context.get("contract_bundle")
    manifest = context.get("asset_manifest")
    if not isinstance(bundle, ContractBundle):
        raise AgentOutputSchemaError("shot_cards requires a formal contract bundle")
    if not isinstance(manifest, AssetManifest):
        raise AgentOutputSchemaError("shot_cards requires an approved asset manifest")
    shots = payload.get("shots")
    if not isinstance(shots, list) or not shots:
        raise AgentOutputSchemaError("shot_cards output must contain at least one shot")
    try:
        cards = tuple(_build_shot_card_from_manifest(item, bundle, manifest) for item in shots)
    except (KeyError, TypeError, ValueError) as exc:
        raise AgentOutputSchemaError(f"shot_cards failed schema validation: {exc}") from exc
    if len({shot.shot_id for shot in cards}) != len(cards):
        raise AgentOutputSchemaError("shot_cards failed schema validation: duplicate shot id")
    return cards


def _validate_image_review_result(payload: dict[str, Any], context: dict[str, Any]) -> VisualReviewResult:
    request = context.get("request")
    if not isinstance(request, VisualReviewRequest):
        raise AgentOutputSchemaError("image_review_result requires the visual review request")
    try:
        if bool(context.get("baseline")):
            return normalize_baseline_review(payload, request)
        return normalize_visual_review(payload, request)
    except (TypeError, ValueError) as exc:
        raise AgentOutputSchemaError(f"image_review_result failed schema validation: {exc}") from exc


def _validate_prompt_set_binding(asset: AssetPlan, visual: Any, prompts: tuple[PromptPlan, ...]) -> None:
    expected = set(asset.planned_images)
    actual = {prompt.image_kind for prompt in prompts}
    if actual != expected or len(prompts) != len(expected):
        raise ValueError(f"prompt set does not cover planned images: expected {sorted(expected)}, got {sorted(actual)}")
    for prompt in prompts:
        if prompt.object_id != asset.asset_id:
            raise ValueError("prompt object id does not match asset")
        if prompt.style_id != getattr(visual, "style_id", ""):
            raise ValueError("prompt style id does not match visual bible")


def _ordered_prompts(asset: AssetPlan, prompts: tuple[PromptPlan, ...]) -> tuple[PromptPlan, ...]:
    by_kind = {prompt.image_kind: prompt for prompt in prompts}
    return tuple(by_kind[kind] for kind in asset.planned_images)


def _build_shot_card_from_manifest(payload: dict[str, Any], bundle: ContractBundle, manifest: AssetManifest) -> ShotCard:
    if not isinstance(payload, dict):
        raise ValueError("shot card must be an object")
    evidence = str(payload.get("evidence_quote") or "").strip()
    if not evidence or evidence not in bundle.creative.source_story:
        raise ValueError("shot card evidence is not present in the confirmed story")
    by_id = {item.asset_id: item for item in manifest.items}
    scene_id = str(payload.get("scene_asset_id") or "").strip()
    if scene_id not in by_id or by_id[scene_id].asset_type != "scene":
        raise ValueError("shot references an invalid scene asset")
    character_ids = tuple(str(value).strip() for value in payload.get("character_asset_ids") or [])
    prop_ids = tuple(str(value).strip() for value in payload.get("prop_asset_ids") or [])
    if any(value not in by_id or by_id[value].asset_type != "character" for value in character_ids):
        raise ValueError("shot references an invalid character asset")
    if any(value not in by_id or by_id[value].asset_type != "prop" for value in prop_ids):
        raise ValueError("shot references an invalid prop asset")
    return build_shot_card(
        payload,
        characters=[by_id[value] for value in character_ids],
        props=[by_id[value] for value in prop_ids],
        scene=by_id[scene_id],
        visual=bundle.visual,
    )


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


_VALIDATORS = {
    "_validate_comic_contract": _validate_comic_contract,
    "_validate_visual_revision": _validate_visual_revision,
    "_validate_asset_manifest": _validate_asset_manifest,
    "_validate_asset_manifest_revision": _validate_asset_manifest_revision,
    "_validate_asset_prompt_set": _validate_asset_prompt_set,
    "_validate_shot_cards": _validate_shot_cards,
    "_validate_image_review_result": _validate_image_review_result,
}
