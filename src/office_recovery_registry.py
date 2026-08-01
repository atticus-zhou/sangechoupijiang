"""Shared audit layer for office recovery actions.

Office profiles declare recovery actions, but product users need more than a
button path: they need to know what survives a retry, what is rebuilt, and which
stage the workflow returns to. This module turns those declarations into an
auditable registry.
"""

from __future__ import annotations

from typing import Any

from src.offices import OFFICE_PROFILES


RECOVERY_CONTRACTS: dict[tuple[str, str], dict[str, Any]] = {
    ("comic_production", "visual_bible_planning"): {
        "preserves": ["confirmed_story", "creative_brief", "workspace_history"],
        "clears": ["story_contract", "visual_bible", "asset_manifest", "downstream_outputs"],
    },
    ("comic_production", "asset_planning"): {
        "preserves": ["confirmed_story", "story_contract", "visual_bible"],
        "clears": ["asset_manifest", "prompt_package", "image_production", "word_canvas"],
    },
    ("comic_production", "asset_review"): {
        "preserves": ["confirmed_story", "story_contract", "visual_bible", "asset_feedback"],
        "clears": ["asset_manifest", "prompt_package", "image_production", "word_canvas"],
    },
    ("comic_production", "prompt_planning"): {
        "preserves": ["confirmed_story", "story_contract", "visual_bible", "asset_manifest"],
        "clears": ["prompt_package", "shot_cards", "image_production", "word_canvas"],
    },
    ("comic_production", "image_generation"): {
        "preserves": ["confirmed_story", "story_contract", "visual_bible", "asset_manifest", "prompt_package"],
        "clears": ["fixture_images", "image_production", "visual_review", "word_canvas"],
    },
    ("comic_production", "visual_review"): {
        "preserves": ["confirmed_story", "story_contract", "visual_bible", "asset_manifest", "prompt_package"],
        "clears": ["visual_review", "image_quality_report", "word_canvas", "handoff_manifest"],
    },
    ("comic_production", "document_generation"): {
        "preserves": ["confirmed_story", "story_contract", "asset_manifest", "prompt_package", "generated_images"],
        "clears": ["word_canvas", "handoff_manifest", "delivery_audit"],
    },
    ("comic_production", "quality_review"): {
        "preserves": ["confirmed_story", "story_contract", "asset_manifest", "prompt_package", "history_trace"],
        "clears": ["image_production", "visual_review", "word_canvas", "handoff_manifest", "claim_report"],
    },
}


def enriched_recovery_actions(office_id: str) -> list[dict[str, Any]]:
    """Return OfficeProfile recovery actions with preserve/clear contracts."""
    office = OFFICE_PROFILES.get(str(office_id or "").strip())
    if not office:
        return []
    return [_enrich_action(office.id, action) for action in office.recovery_actions]


def list_office_recovery_action_bindings() -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for office_id, office in sorted(OFFICE_PROFILES.items()):
        for action in office.recovery_actions:
            enriched = _enrich_action(office_id, action)
            bindings.append(_binding_for_action(office_id, enriched))
    return bindings


def audit_office_recovery_registry() -> dict[str, Any]:
    bindings = list_office_recovery_action_bindings()
    errors = [item for item in bindings if item["status"] != "passed"]
    offices_with_actions = sorted({item["office_id"] for item in bindings})
    recovery_stage_count = {
        office_id: len([item for item in bindings if item["office_id"] == office_id])
        for office_id in offices_with_actions
    }
    return {
        "status": "passed" if not errors else "needs_work",
        "offices_with_actions": offices_with_actions,
        "binding_count": len(bindings),
        "passed_binding_count": len(bindings) - len(errors),
        "error_count": len(errors),
        "recovery_stage_count": recovery_stage_count,
        "bindings": bindings,
    }


def _enrich_action(office_id: str, action: dict[str, Any]) -> dict[str, Any]:
    stage = str(action.get("stage") or "").strip()
    contract = RECOVERY_CONTRACTS.get((office_id, stage), {})
    enriched = dict(action)
    if contract:
        enriched.setdefault("preserves", list(contract.get("preserves") or []))
        enriched.setdefault("clears", list(contract.get("clears") or []))
    return enriched


def _binding_for_action(office_id: str, action: dict[str, Any]) -> dict[str, Any]:
    stage = str(action.get("stage") or "").strip()
    method = str(action.get("method") or "").strip()
    path_template = str(action.get("path_template") or "").strip()
    preserves = list(action.get("preserves") or [])
    clears = list(action.get("clears") or [])
    errors: list[str] = []
    if not stage:
        errors.append("missing stage")
    if method not in {"POST", "PUT", "PATCH"}:
        errors.append("recovery action must use a mutating HTTP method")
    if not path_template.startswith("/api/"):
        errors.append("recovery action must expose an API path_template")
    if "{workspace_id}" not in path_template and "{task_id}" not in path_template:
        errors.append("path_template must be scoped by workspace_id or task_id")
    if not preserves:
        errors.append("missing preserves contract")
    if not clears:
        errors.append("missing clears contract")
    if set(preserves) & set(clears):
        errors.append("preserves and clears must not overlap")
    return {
        "office_id": office_id,
        "stage": stage,
        "label": str(action.get("label") or ""),
        "method": method,
        "path_template": path_template,
        "preserves": preserves,
        "clears": clears,
        "has_body_contract": bool(action.get("body_contract")),
        "status": "passed" if not errors else "needs_work",
        "errors": errors,
    }
