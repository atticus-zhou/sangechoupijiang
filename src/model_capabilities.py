"""Machine-readable model capability requirements for offices.

This module is intentionally no-key and side-effect free. It only reads the
public capability matrix used by docs, first-run checks, and office preflight.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO_ROOT / "docs" / "MODEL_CAPABILITY_MATRIX.json"


@lru_cache(maxsize=1)
def load_model_capability_matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def get_office_capability_contract(office_id: str) -> dict[str, Any]:
    normalized = "comic_production" if office_id == "comic" else office_id
    matrix = load_model_capability_matrix()
    office = (matrix.get("offices") or {}).get(normalized, {})
    return {
        "schema": matrix.get("schema"),
        "source": "docs/MODEL_CAPABILITY_MATRIX.json",
        "office_id": normalized,
        "office_name": office.get("office_name", normalized),
        "minimum_mode": office.get("minimum_mode", ""),
        "full_mode": office.get("full_mode", ""),
        "minimum_ready_when": office.get("minimum_ready_when", ""),
        "full_ready_when": office.get("full_ready_when", ""),
        "departments": list(office.get("departments") or []),
        "capability_kinds": matrix.get("capability_kinds") or {},
        "safe_key_rule": matrix.get("safe_key_rule", ""),
    }


def summarize_office_capability_contract(office_id: str) -> dict[str, Any]:
    contract = get_office_capability_contract(office_id)
    departments = contract.get("departments") or []
    capability_counts: dict[str, int] = {}
    for department in departments:
        capability = str(department.get("required_capability") or "unknown")
        capability_counts[capability] = capability_counts.get(capability, 0) + 1
    return {
        "schema": contract.get("schema"),
        "source": contract.get("source"),
        "office_id": contract.get("office_id"),
        "office_name": contract.get("office_name"),
        "minimum_mode": contract.get("minimum_mode"),
        "full_mode": contract.get("full_mode"),
        "department_count": len(departments),
        "capability_counts": capability_counts,
        "minimum_ready_when": contract.get("minimum_ready_when"),
        "full_ready_when": contract.get("full_ready_when"),
    }
