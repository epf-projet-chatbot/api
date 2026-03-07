"""Utility helpers for normalization, formatting and post-processing."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(text: str) -> str:
    """Normalize text for robust matching (accents/case/spacing)."""

    base = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(ch for ch in base if not unicodedata.combining(ch))
    lowered = ascii_text.lower()
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def format_conversation_history(messages: list[dict[str, Any]] | None) -> str:
    """Format conversation history for prompt injection."""

    if not messages:
        return ""

    rendered: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = str(message.get("content", "")).strip()
        prefix = "Utilisateur" if role == "user" else "Badinter"
        rendered.append(f"{prefix}: {content}")
    return "\n".join(rendered)


def clean_final_answer(answer: str) -> str:
    """Clean model artefacts and trim final answer."""

    cleaned = re.sub(r"TEMPLATE_REQUEST:\s*.+?(?:\n|$)", "", answer or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,;:.!?])", r"\1", cleaned)
    cleaned = cleaned.strip()
    return cleaned


def ensure_sources_section(answer: str, source_blocks: list[dict[str, str]]) -> str:
    """Guarantee a Markdown sources section exists."""

    if "## Sources" in answer:
        return answer

    if not source_blocks:
        return f"{answer}\n\n## Sources\n- Aucune source documentaire exploitable trouvée."

    lines = ["## Sources"]
    for block in source_blocks:
        source = block.get("source", "source inconnue")
        page = str(block.get("page", "?"))
        section = block.get("section", "")
        suffix = f" | section={section}" if section else ""
        lines.append(f"- document={source} | page={page}{suffix}")

    return f"{answer}\n\n" + "\n".join(lines)
