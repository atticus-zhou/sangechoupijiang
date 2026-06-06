"""Research-office domain helpers."""

from .workflow import (
    build_evidence_fallback_result,
    format_workspace_evidence_context,
    needs_platform_evidence,
    research_capture_keyword,
)

__all__ = [
    "build_evidence_fallback_result",
    "format_workspace_evidence_context",
    "needs_platform_evidence",
    "research_capture_keyword",
]
