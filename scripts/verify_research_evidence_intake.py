"""Verify a research-office evidence intake file before rebuilding reports.

The default input is the public template. Operators can pass a filled JSON file
captured after human login/screenshot work:

    python scripts/verify_research_evidence_intake.py --input path/to/intake.json

This verifier is intentionally offline. It does not log in, scrape platforms,
read API keys, or touch user workspaces. It only answers whether the evidence
package is structurally safe enough to use for report rebuild decisions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "docs" / "RESEARCH_EVIDENCE_INTAKE_TEMPLATE.json"

SECRET_PATTERNS = {
    "openai_style_secret": re.compile(r"sk-[A-Za-z0-9_-]{16,}", re.I),
    "long_api_key_assignment": re.compile(r"api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_-]{12,}", re.I),
    "cookie_header": re.compile(r"\bCookie\s*[:=]", re.I),
    "password_assignment": re.compile(r"password\s*[:=]\s*['\"]?\S{6,}", re.I),
    "windows_browser_profile": re.compile(r"[A-Z]:\\\\.*(User Data|Cookies|Local State)", re.I),
}

REQUIRED_TOP_LEVEL = [
    "schema",
    "office_id",
    "claim_boundary",
    "workspace",
    "source_records",
    "screenshot_records",
    "data_rows",
    "claim_records",
    "evidence_gap_cards",
    "report_rebuild",
    "operator_acceptance_checklist",
    "research_evidence_summary",
]

REQUIRED_SOURCE_FIELDS = [
    "source_id",
    "title",
    "source_type",
    "url_or_local_ref",
    "access_mode",
    "captured_by",
    "captured_at",
    "status",
    "sensitive_material_removed",
]

REQUIRED_SCREENSHOT_FIELDS = [
    "evidence_id",
    "source_id",
    "file_name",
    "page_or_panel",
    "claim_ids",
    "capture_method",
    "contains_private_account_data",
    "redaction_required",
    "status",
]

REQUIRED_DATA_FIELDS = [
    "row_id",
    "source_id",
    "evidence_id",
    "metric",
    "value",
    "unit",
    "time_range",
    "status",
]

REQUIRED_CLAIM_FIELDS = [
    "claim_id",
    "claim_text",
    "evidence_ids",
    "source_ids",
    "data_row_ids",
    "confidence",
    "report_section",
]


def _load_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not path.exists():
        return {}, [f"input file is missing: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        return {}, [f"input must be UTF-8 JSON: {exc}"]
    except json.JSONDecodeError as exc:
        return {}, [f"input is not valid JSON: {exc}"]
    if not isinstance(payload, dict):
        errors.append("input JSON must be an object")
        payload = {}
    return payload, errors


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _missing_fields(item: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if item.get(field) in (None, "", [])]


def _as_id_set(items: list[dict[str, Any]], key: str) -> set[str]:
    return {str(item.get(key) or "") for item in items if item.get(key)}


def _placeholder_paths(payload: Any, path: str = "$") -> list[str]:
    placeholders: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            placeholders.extend(_placeholder_paths(value, f"{path}.{key}"))
        return placeholders
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            placeholders.extend(_placeholder_paths(value, f"{path}[{index}]"))
        return placeholders
    if isinstance(payload, str):
        lowered = payload.lower()
        if "replace_" in lowered or "_replace" in lowered or "replace/" in lowered or "2026-01-01t00:00:00z" in lowered:
            placeholders.append(path)
    return placeholders


def verify_research_evidence_intake(input_path: Path = DEFAULT_INPUT, *, strict_real_values: bool = False) -> dict[str, Any]:
    input_path = Path(input_path)
    payload, errors = _load_json(input_path)
    warnings: list[str] = []

    if payload:
        text = _json_text(payload)
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"intake appears to contain forbidden sensitive marker: {label}")

        for field in REQUIRED_TOP_LEVEL:
            if field not in payload:
                errors.append(f"top-level field missing: {field}")

        if payload.get("schema") != "research_evidence_intake_v1":
            errors.append("schema must be research_evidence_intake_v1")
        if payload.get("office_id") != "research":
            errors.append("office_id must be research")
        if strict_real_values:
            placeholder_fields = _placeholder_paths(payload)
            if placeholder_fields:
                errors.append(
                    "intake still contains placeholder values: "
                    + ", ".join(placeholder_fields[:12])
                    + (" ..." if len(placeholder_fields) > 12 else "")
                )

        claim_boundary = payload.get("claim_boundary") or {}
        must_not_include = set(claim_boundary.get("must_not_include") or [])
        for marker in ("api_key", "cookie", "account_password", "raw_private_dashboard_export"):
            if marker not in must_not_include:
                errors.append(f"claim_boundary.must_not_include missing {marker}")
        allowed_after = set(claim_boundary.get("public_claim_allowed_only_after") or [])
        for marker in (
            "all_key_claims_have_source_or_screenshot",
            "pending_account_or_manual_capture_is_zero",
            "placeholder_demo_source_is_zero",
            "evidence_manifest_passes_schema_gate",
            "report_rebuilt_after_evidence_update",
        ):
            if marker not in allowed_after:
                errors.append(f"claim_boundary.public_claim_allowed_only_after missing {marker}")

        sources = payload.get("source_records") or []
        screenshots = payload.get("screenshot_records") or []
        data_rows = payload.get("data_rows") or []
        claims = payload.get("claim_records") or []
        gap_cards = payload.get("evidence_gap_cards") or []
        if not sources:
            errors.append("source_records must not be empty")
        if not screenshots:
            errors.append("screenshot_records must not be empty")
        if not claims:
            errors.append("claim_records must not be empty")

        source_ids = _as_id_set(sources, "source_id")
        evidence_ids = _as_id_set(screenshots, "evidence_id")
        data_row_ids = _as_id_set(data_rows, "row_id")
        claim_ids = _as_id_set(claims, "claim_id")

        for index, item in enumerate(sources):
            missing = _missing_fields(item, REQUIRED_SOURCE_FIELDS)
            if missing:
                errors.append(f"source_records[{index}] missing fields: {', '.join(missing)}")
            if item.get("sensitive_material_removed") is not True:
                errors.append(f"source_records[{index}] must mark sensitive_material_removed=true")

        for index, item in enumerate(screenshots):
            missing = _missing_fields(item, REQUIRED_SCREENSHOT_FIELDS)
            if missing:
                errors.append(f"screenshot_records[{index}] missing fields: {', '.join(missing)}")
            source_id = str(item.get("source_id") or "")
            if source_id and source_id not in source_ids:
                errors.append(f"screenshot_records[{index}] references unknown source_id: {source_id}")
            if not str(item.get("file_name") or "").startswith("evidence_"):
                errors.append(f"screenshot_records[{index}] file_name must start with evidence_")
            if item.get("contains_private_account_data") is not False:
                errors.append(f"screenshot_records[{index}] must remove private account data")
            for claim_id in item.get("claim_ids") or []:
                if str(claim_id) not in claim_ids:
                    errors.append(f"screenshot_records[{index}] references unknown claim_id: {claim_id}")

        for index, item in enumerate(data_rows):
            missing = _missing_fields(item, REQUIRED_DATA_FIELDS)
            if missing:
                errors.append(f"data_rows[{index}] missing fields: {', '.join(missing)}")
            if item.get("source_id") and str(item.get("source_id")) not in source_ids:
                errors.append(f"data_rows[{index}] references unknown source_id: {item.get('source_id')}")
            if item.get("evidence_id") and str(item.get("evidence_id")) not in evidence_ids:
                errors.append(f"data_rows[{index}] references unknown evidence_id: {item.get('evidence_id')}")

        for index, item in enumerate(claims):
            missing = _missing_fields(item, REQUIRED_CLAIM_FIELDS)
            if missing:
                errors.append(f"claim_records[{index}] missing fields: {', '.join(missing)}")
            if not item.get("evidence_ids") and not item.get("source_ids") and not item.get("data_row_ids"):
                errors.append(f"claim_records[{index}] must cite evidence, source, or data rows")
            for evidence_id in item.get("evidence_ids") or []:
                if str(evidence_id) not in evidence_ids:
                    errors.append(f"claim_records[{index}] references unknown evidence_id: {evidence_id}")
            for source_id in item.get("source_ids") or []:
                if str(source_id) not in source_ids:
                    errors.append(f"claim_records[{index}] references unknown source_id: {source_id}")
            for row_id in item.get("data_row_ids") or []:
                if str(row_id) not in data_row_ids:
                    errors.append(f"claim_records[{index}] references unknown data_row_id: {row_id}")

        for index, item in enumerate(gap_cards):
            for field in ("gap_id", "claim_id", "missing_evidence", "owner", "suggested_file_name", "acceptance", "after_capture_action"):
                if item.get(field) in (None, "", []):
                    errors.append(f"evidence_gap_cards[{index}] missing {field}")
            if item.get("claim_id") and str(item.get("claim_id")) not in claim_ids:
                errors.append(f"evidence_gap_cards[{index}] references unknown claim_id: {item.get('claim_id')}")
            if item.get("suggested_file_name") and not str(item.get("suggested_file_name")).startswith("evidence_"):
                errors.append(f"evidence_gap_cards[{index}] suggested_file_name must start with evidence_")

        rebuild = payload.get("report_rebuild") or {}
        if rebuild.get("required_after_evidence_update") is not True:
            errors.append("report_rebuild.required_after_evidence_update must be true")
        commands = "\n".join(str(item) for item in rebuild.get("commands") or [])
        if "verify_research_office_readiness.py" not in commands:
            errors.append("report_rebuild.commands must include verify_research_office_readiness.py")
        must_update = set(rebuild.get("must_update") or [])
        for target in ("report.md", "evidence_manifest.json", "claim-report.json"):
            if target not in must_update:
                errors.append(f"report_rebuild.must_update missing {target}")

        acceptance = payload.get("operator_acceptance_checklist") or {}
        if acceptance.get("staged_delivery_approved") is not True:
            errors.append("operator_acceptance_checklist.staged_delivery_approved must be true")
        if acceptance.get("final_claim_approved") is True and gap_cards:
            errors.append("final_claim_approved cannot be true while evidence_gap_cards still exist")
        if acceptance.get("final_claim_approved") is True and acceptance.get("report_rebuilt_after_evidence_update") is not True:
            errors.append("final_claim_approved requires report_rebuilt_after_evidence_update=true")

        summary = payload.get("research_evidence_summary") or {}
        expected_counts = {
            "source_count": len(sources),
            "screenshot_count": len(screenshots),
            "verified_claim_count": sum(1 for item in claims if item.get("confidence") == "verified"),
            "pending_gap_count": len(gap_cards),
        }
        for field, expected in expected_counts.items():
            actual = int(summary.get(field) or 0)
            if actual != expected:
                errors.append(f"research_evidence_summary.{field} expected {expected}, got {actual}")
        if int(summary.get("placeholder_demo_source_count") or 0) > 0:
            warnings.append("placeholder demo sources remain; final research claim should stay blocked")
        ready_for_final = summary.get("ready_for_final_research_claim") is True
        if ready_for_final and gap_cards:
            errors.append("ready_for_final_research_claim cannot be true while pending gaps exist")
        if ready_for_final and acceptance.get("final_claim_approved") is not True:
            errors.append("ready_for_final_research_claim requires final_claim_approved=true")

    summary = payload.get("research_evidence_summary") or {}
    acceptance = payload.get("operator_acceptance_checklist") or {}
    result = {
        "status": "passed" if not errors else "failed",
        "mode": "research_evidence_intake",
        "input": str(input_path.relative_to(REPO_ROOT) if input_path.is_relative_to(REPO_ROOT) else input_path),
        "strict_real_values": strict_real_values,
        "summary": (
            "Research evidence intake is structurally safe and ready for staged report rebuild decisions."
            if not errors
            else "Research evidence intake has blocking issues."
        ),
        "source_count": len(payload.get("source_records") or []) if payload else 0,
        "screenshot_count": len(payload.get("screenshot_records") or []) if payload else 0,
        "data_row_count": len(payload.get("data_rows") or []) if payload else 0,
        "claim_count": len(payload.get("claim_records") or []) if payload else 0,
        "gap_card_count": len(payload.get("evidence_gap_cards") or []) if payload else 0,
        "summary_ready_for_final": summary.get("ready_for_final_research_claim"),
        "operator_staged_approved": acceptance.get("staged_delivery_approved"),
        "operator_final_approved": acceptance.get("final_claim_approved"),
        "report_rebuilt_after_evidence_update": acceptance.get("report_rebuilt_after_evidence_update"),
        "warnings": warnings,
        "errors": errors,
    }
    return result


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Research Evidence Intake Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Input: `{payload.get('input')}`",
        f"Strict real values: `{payload.get('strict_real_values')}`",
        f"Summary: {payload.get('summary')}",
        "",
        f"- Sources: {payload.get('source_count')}",
        f"- Screenshots: {payload.get('screenshot_count')}",
        f"- Data rows: {payload.get('data_row_count')}",
        f"- Claims: {payload.get('claim_count')}",
        f"- Evidence gaps: {payload.get('gap_card_count')}",
        f"- Staged approved: {payload.get('operator_staged_approved')}",
        f"- Final approved: {payload.get('operator_final_approved')}",
        f"- Report rebuilt after evidence update: {payload.get('report_rebuilt_after_evidence_update')}",
        f"- Ready for final research claim: {payload.get('summary_ready_for_final')}",
    ]
    if payload.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in payload["warnings"])
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--strict-real-values",
        action="store_true",
        help="Reject placeholder values such as replace_... when auditing a filled real evidence file.",
    )
    parser.add_argument("--format", choices={"json", "markdown"}, default="markdown")
    args = parser.parse_args()
    payload = verify_research_evidence_intake(args.input, strict_real_values=args.strict_real_values)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
