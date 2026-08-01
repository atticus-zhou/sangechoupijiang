"""Shared audit layer for office-specific schema gates.

Office profiles declare which model outputs must pass schema gates. The
validators still live inside each office package, but this module proves that a
declared gate is backed by a concrete validator before an office can be treated
as productized.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.comic_office.v2.output_schemas import (
    list_agent_output_schemas,
    validate_agent_output_schema,
)
from src.offices import OFFICE_PROFILES
from src.research_office.output_schemas import (
    list_research_output_schemas,
    validate_research_output_schema,
)


Validator = Callable[..., Any]


@dataclass(frozen=True)
class OfficeSchemaProvider:
    office_id: str
    list_schemas: Callable[[], list[dict[str, Any]]]
    validate_schema: Validator
    smoke_payloads: dict[str, dict[str, Any]]


def _list_comic_schemas() -> list[dict[str, Any]]:
    return list_agent_output_schemas("comic_production")


SCHEMA_PROVIDERS: dict[str, OfficeSchemaProvider] = {
    "comic_production": OfficeSchemaProvider(
        office_id="comic_production",
        list_schemas=_list_comic_schemas,
        validate_schema=validate_agent_output_schema,
        smoke_payloads={
            "comic_contract": {},
            "visual_revision": {},
            "asset_manifest": {},
            "asset_manifest_revision": {},
            "asset_prompt_set": {},
            "shot_cards": {},
            "image_review_result": {},
        },
    ),
    "research": OfficeSchemaProvider(
        office_id="research",
        list_schemas=list_research_output_schemas,
        validate_schema=validate_research_output_schema,
        smoke_payloads={
            "research_standard_report": {},
            "research_source_list": {},
            "research_data_table": {},
            "research_competitor_table": {},
        },
    ),
}


def list_office_schema_gate_bindings() -> list[dict[str, Any]]:
    """Return every declared office schema gate and its concrete binding."""
    bindings: list[dict[str, Any]] = []
    for office_id, office in sorted(OFFICE_PROFILES.items()):
        provider = SCHEMA_PROVIDERS.get(office_id)
        concrete_by_id = _schemas_by_id(provider) if provider else {}
        for gate in office.schema_gates:
            schema_id = str(gate.get("schema_id") or "").strip()
            concrete = concrete_by_id.get(schema_id)
            bindings.append(_binding_for_gate(office_id, gate, concrete, provider))
        if provider:
            declared_ids = {str(gate.get("schema_id") or "").strip() for gate in office.schema_gates}
            for schema_id, schema in sorted(concrete_by_id.items()):
                if schema_id not in declared_ids:
                    bindings.append(_orphan_binding(office_id, schema, provider))
    return bindings


def audit_office_schema_gate_registry() -> dict[str, Any]:
    """Audit that declared schema gates are backed by office validators."""
    bindings = list_office_schema_gate_bindings()
    offices_with_declared_gates = sorted({
        item["office_id"]
        for item in bindings
        if item["binding_status"] != "orphan_concrete_schema"
    })
    provider_offices = sorted(SCHEMA_PROVIDERS)
    missing_provider_offices = sorted(
        office_id
        for office_id, office in OFFICE_PROFILES.items()
        if office.schema_gates and office_id not in SCHEMA_PROVIDERS
    )
    errors = [
        item
        for item in bindings
        if item["status"] != "passed"
    ]
    missing_schema_ids = sorted({
        item["schema_id"]
        for item in errors
        if item["binding_status"] == "missing_concrete_schema"
    })
    orphan_schema_ids = sorted({
        item["schema_id"]
        for item in errors
        if item["binding_status"] == "orphan_concrete_schema"
    })
    return {
        "status": "passed" if not errors and not missing_provider_offices else "needs_work",
        "provider_offices": provider_offices,
        "offices_with_declared_gates": offices_with_declared_gates,
        "missing_provider_offices": missing_provider_offices,
        "binding_count": len(bindings),
        "passed_binding_count": len([item for item in bindings if item["status"] == "passed"]),
        "error_count": len(errors) + len(missing_provider_offices),
        "missing_schema_ids": missing_schema_ids,
        "orphan_schema_ids": orphan_schema_ids,
        "bindings": bindings,
    }


def _schemas_by_id(provider: OfficeSchemaProvider | None) -> dict[str, dict[str, Any]]:
    if not provider:
        return {}
    return {
        str(schema.get("schema_id") or "").strip(): schema
        for schema in provider.list_schemas()
        if str(schema.get("schema_id") or "").strip()
    }


def _binding_for_gate(
    office_id: str,
    gate: dict[str, Any],
    schema: dict[str, Any] | None,
    provider: OfficeSchemaProvider | None,
) -> dict[str, Any]:
    schema_id = str(gate.get("schema_id") or "").strip()
    artifact_type = str(gate.get("artifact_type") or "").strip()
    office = OFFICE_PROFILES[office_id]
    errors: list[str] = []
    if provider is None:
        errors.append("office has declared schema gates but no schema provider")
    if schema is None:
        errors.append("declared schema gate has no concrete validator schema")
    if artifact_type and artifact_type not in office.artifact_types:
        errors.append("schema gate artifact_type is not declared in the office artifact contract")
    if schema:
        if schema.get("office_id") != office_id:
            errors.append("concrete schema office_id does not match the OfficeProfile id")
        for field in ("owner_agent", "stage", "required_fields", "failure_impact"):
            if not schema.get(field):
                errors.append(f"concrete schema missing {field}")
        if gate.get("owner_agent") and schema.get("owner_agent") != gate.get("owner_agent"):
            errors.append("owner_agent differs between OfficeProfile and concrete schema")
        if gate.get("stage") and schema.get("stage") != gate.get("stage"):
            errors.append("stage differs between OfficeProfile and concrete schema")
    return {
        "office_id": office_id,
        "schema_id": schema_id,
        "artifact_type": artifact_type,
        "owner_agent": gate.get("owner_agent") or "",
        "stage": gate.get("stage") or "",
        "binding_status": "bound" if schema else "missing_concrete_schema",
        "validator_provider": provider.office_id if provider else "",
        "status": "passed" if not errors else "needs_work",
        "errors": errors,
    }


def _orphan_binding(
    office_id: str,
    schema: dict[str, Any],
    provider: OfficeSchemaProvider,
) -> dict[str, Any]:
    return {
        "office_id": office_id,
        "schema_id": str(schema.get("schema_id") or ""),
        "artifact_type": "",
        "owner_agent": str(schema.get("owner_agent") or ""),
        "stage": str(schema.get("stage") or ""),
        "binding_status": "orphan_concrete_schema",
        "validator_provider": provider.office_id,
        "status": "needs_work",
        "errors": ["concrete schema exists but OfficeProfile does not declare it"],
    }
