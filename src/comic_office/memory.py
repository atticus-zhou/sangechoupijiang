"""Core memory vault for long AI comic conversations."""

from __future__ import annotations


def build_core_memory_vault(session: dict) -> dict:
    """Extract stable story settings from a noisy cabinet session."""
    creative = session.get("creative_brief") or {}
    script = session.get("confirmed_script") or session.get("script_preview") or {}
    notes = [str(item).strip() for item in (session.get("user_notes") or []) if str(item).strip()]
    return {
        "title": script.get("title") or creative.get("title") or session.get("idea", ""),
        "core_idea": creative.get("core_idea") or session.get("idea", ""),
        "genre": script.get("genre") or creative.get("genre") or session.get("genre", ""),
        "visual_style": creative.get("visual_style") or session.get("visual_style", ""),
        "story_promise": creative.get("story_promise", ""),
        "main_conflict": creative.get("main_conflict", ""),
        "why_it_happens": script.get("why_it_happens", ""),
        "how_it_happens": script.get("how_it_happens", ""),
        "protagonist_arc": script.get("protagonist_arc", ""),
        "locked_user_notes": notes[-5:],
        "conversation_window": _recent_messages(session, limit=3),
    }


def build_memory_context_prompt(vault: dict) -> str:
    """Render a compact prompt block that can be injected into LLM calls."""
    lines = [
        "[Core memory vault]",
        f"Title: {vault.get('title', '')}",
        f"Core idea: {vault.get('core_idea', '')}",
        f"Genre: {vault.get('genre', '')}",
        f"Visual style: {vault.get('visual_style', '')}",
        f"Story promise: {vault.get('story_promise', '')}",
        f"Main conflict: {vault.get('main_conflict', '')}",
        f"Why it happens: {vault.get('why_it_happens', '')}",
        f"How it happens: {vault.get('how_it_happens', '')}",
        f"Protagonist arc: {vault.get('protagonist_arc', '')}",
        "Locked user notes:",
    ]
    notes = vault.get("locked_user_notes") or []
    lines.extend([f"- {item}" for item in notes] or ["-"])
    lines.append("Recent conversation window:")
    lines.extend([f"- {item}" for item in (vault.get("conversation_window") or [])] or ["-"])
    return "\n".join(lines)


def _recent_messages(session: dict, limit: int = 3) -> list[str]:
    messages = session.get("messages") or []
    rendered = []
    for item in messages[-limit:]:
        role = item.get("role", "")
        content = str(item.get("content", "")).strip()
        if content:
            rendered.append(f"{role}: {content}")
    return rendered
