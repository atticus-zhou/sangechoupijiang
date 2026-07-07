"""Schema registry for model outputs in the comic-production V2 pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .contracts import (
    ContractBundle,
    ContractValidationError,
    build_contract_bundle,
)
from .asset_manifest import (
    AssetManifest,
    ManifestValidationError,
    NoManifestChangeError,
    build_asset_manifest,
    replace_asset_manifest,
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
) -> ContractBundle | AssetManifest:
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
}
