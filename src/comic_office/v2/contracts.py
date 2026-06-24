"""Immutable creative contracts for the V2 comic production pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


class ContractValidationError(ValueError):
    """Raised when a planner response cannot become a formal contract."""


def story_hash(source_story: str) -> str:
    """Return a stable hash without normalizing or rewriting the story."""
    return hashlib.sha256((source_story or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EpisodeContract:
    episode: int
    summary: str
    evidence_quote: str


@dataclass(frozen=True)
class CreativeContract:
    story_id: str
    story_version: int
    source_mode: str
    source_hash: str
    source_story: str
    title: str
    genre: str
    theme: str
    protagonist_goal: str
    main_conflict: str
    causal_chain: tuple[str, ...]
    ending: str
    episodes: tuple[EpisodeContract, ...]
    must_keep: tuple[str, ...]
    must_avoid: tuple[str, ...]


@dataclass(frozen=True)
class VisualBible:
    style_id: str
    style_version: int
    story_id: str
    story_version: int
    medium: str
    era: str
    aspect_ratio: str
    palette: tuple[str, ...]
    lighting: str
    camera_language: str
    character_rules: tuple[str, ...]
    costume_rules: tuple[str, ...]
    prop_rules: tuple[str, ...]
    architecture_rules: tuple[str, ...]
    visual_motifs: tuple[str, ...]
    prohibited_elements: tuple[str, ...]


@dataclass(frozen=True)
class ContractBundle:
    creative: CreativeContract
    visual: VisualBible
    status: str = "visual_bible_review"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CREATIVE_REQUIRED = (
    "title",
    "genre",
    "theme",
    "protagonist_goal",
    "main_conflict",
    "causal_chain",
    "ending",
    "episodes",
)

_VISUAL_REQUIRED = (
    "medium",
    "era",
    "aspect_ratio",
    "palette",
    "lighting",
    "camera_language",
    "character_rules",
    "costume_rules",
    "prop_rules",
    "architecture_rules",
    "visual_motifs",
    "prohibited_elements",
)


def build_contract_bundle(
    source_story: str,
    planner_payload: dict[str, Any],
    *,
    source_mode: str = "full_story",
    story_version: int = 1,
    style_version: int = 1,
) -> ContractBundle:
    """Build a formal bundle from an already confirmed story and planner JSON."""
    source = source_story if isinstance(source_story, str) else ""
    if not source.strip():
        raise ContractValidationError("confirmed story is empty")
    if not isinstance(planner_payload, dict):
        raise ContractValidationError("planner payload must be an object")
    _require_fields(planner_payload, _CREATIVE_REQUIRED, "creative contract")
    visual_payload = planner_payload.get("visual")
    if not isinstance(visual_payload, dict):
        raise ContractValidationError("visual bible is missing")
    _require_fields(visual_payload, _VISUAL_REQUIRED, "visual bible")

    digest = story_hash(source)
    story_id = f"story_{digest[:12]}"
    episodes = tuple(_episode_contract(item, source) for item in planner_payload["episodes"])
    creative = CreativeContract(
        story_id=story_id,
        story_version=_positive_version(story_version, "story_version"),
        source_mode=(source_mode or "full_story").strip(),
        source_hash=digest,
        source_story=source,
        title=str(planner_payload["title"]).strip(),
        genre=str(planner_payload["genre"]).strip(),
        theme=str(planner_payload["theme"]).strip(),
        protagonist_goal=str(planner_payload["protagonist_goal"]).strip(),
        main_conflict=str(planner_payload["main_conflict"]).strip(),
        causal_chain=_string_tuple(planner_payload["causal_chain"], "causal_chain"),
        ending=str(planner_payload["ending"]).strip(),
        episodes=episodes,
        must_keep=_optional_string_tuple(planner_payload.get("must_keep")),
        must_avoid=_optional_string_tuple(planner_payload.get("must_avoid")),
    )
    style_payload = json.dumps(visual_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    style_digest = hashlib.sha256(f"{story_id}:{style_version}:{style_payload}".encode("utf-8")).hexdigest()
    visual = VisualBible(
        style_id=f"style_{style_digest[:12]}",
        style_version=_positive_version(style_version, "style_version"),
        story_id=story_id,
        story_version=creative.story_version,
        medium=str(visual_payload["medium"]).strip(),
        era=str(visual_payload["era"]).strip(),
        aspect_ratio=str(visual_payload["aspect_ratio"]).strip(),
        palette=_string_tuple(visual_payload["palette"], "palette"),
        lighting=str(visual_payload["lighting"]).strip(),
        camera_language=str(visual_payload["camera_language"]).strip(),
        character_rules=_string_tuple(visual_payload["character_rules"], "character_rules"),
        costume_rules=_string_tuple(visual_payload["costume_rules"], "costume_rules"),
        prop_rules=_string_tuple(visual_payload["prop_rules"], "prop_rules"),
        architecture_rules=_string_tuple(visual_payload["architecture_rules"], "architecture_rules"),
        visual_motifs=_string_tuple(visual_payload["visual_motifs"], "visual_motifs"),
        prohibited_elements=_string_tuple(visual_payload["prohibited_elements"], "prohibited_elements"),
    )
    bundle = ContractBundle(creative=creative, visual=visual)
    validate_contract_bundle(bundle)
    return bundle


def validate_contract_bundle(bundle: ContractBundle) -> None:
    if bundle.visual.story_id != bundle.creative.story_id:
        raise ContractValidationError("visual bible belongs to another story")
    if bundle.visual.story_version != bundle.creative.story_version:
        raise ContractValidationError("visual bible targets another story version")
    if bundle.creative.source_hash != story_hash(bundle.creative.source_story):
        raise ContractValidationError("confirmed story was modified")


def contract_bundle_from_dict(payload: dict[str, Any]) -> ContractBundle:
    """Restore a persisted bundle through the same validation used for model output."""
    if not isinstance(payload, dict):
        raise ContractValidationError("contract payload must be an object")
    creative = payload.get("creative") or {}
    visual = payload.get("visual") or {}
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
        "visual": {
            key: value
            for key, value in visual.items()
            if key not in {"style_id", "style_version", "story_id", "story_version"}
        },
    }
    restored = build_contract_bundle(
        str(creative.get("source_story") or ""),
        planner_payload,
        source_mode=str(creative.get("source_mode") or "full_story"),
        story_version=int(creative.get("story_version") or 1),
        style_version=int(visual.get("style_version") or 1),
    )
    if restored.creative.story_id != str(creative.get("story_id") or ""):
        raise ContractValidationError("persisted story id does not match")
    if restored.visual.style_id != str(visual.get("style_id") or ""):
        raise ContractValidationError("persisted style id does not match")
    return ContractBundle(
        creative=restored.creative,
        visual=restored.visual,
        status=str(payload.get("status") or restored.status),
    )


def _episode_contract(payload: Any, source_story: str) -> EpisodeContract:
    if not isinstance(payload, dict):
        raise ContractValidationError("episode must be an object")
    _require_fields(payload, ("episode", "summary", "evidence_quote"), "episode")
    evidence = str(payload["evidence_quote"]).strip()
    if evidence not in source_story:
        raise ContractValidationError("episode evidence is not present in the confirmed story")
    try:
        episode_number = int(payload["episode"])
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("episode number must be an integer") from exc
    if episode_number < 1:
        raise ContractValidationError("episode number must be positive")
    return EpisodeContract(
        episode=episode_number,
        summary=str(payload["summary"]).strip(),
        evidence_quote=evidence,
    )


def _require_fields(payload: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if not _has_value(payload.get(field))]
    if missing:
        raise ContractValidationError(f"{label} missing fields: {', '.join(missing)}")


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    result = _optional_string_tuple(value)
    if not result:
        raise ContractValidationError(f"{label} must contain at least one item")
    return result


def _optional_string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ContractValidationError("list field must be an array")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _positive_version(value: Any, label: str) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{label} must be an integer") from exc
    if version < 1:
        raise ContractValidationError(f"{label} must be positive")
    return version
