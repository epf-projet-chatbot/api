"""Template/document detection with deterministic-first strategy."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Optional

from .utils import normalize_text


STRONG_DOCUMENT_REQUEST_MARKERS = [
    "template", "modele", "exemple de document", "document a remplir",
    "fichier", "telecharger", "telecharge", "formulaire", "trame",
    "envoie moi le document", "envoie moi un document", "donne moi le document", "peux tu me fournir le document",
    "j ai besoin du template", "fournis moi",
]

WEAK_DOCUMENT_TERMS = [
    "avenant", "convention", "bon de commande", "pv", "proces verbal", "procès verbal", "rm",
]


def _fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(a=normalize_text(a), b=normalize_text(b)).ratio()


def _contains_strong_document_request(normalized_query: str) -> bool:
    for marker in STRONG_DOCUMENT_REQUEST_MARKERS:
        marker_norm = normalize_text(marker)
        if marker_norm in normalized_query:
            return True
        if _fuzzy_ratio(normalized_query, marker_norm) >= 0.82:
            return True

    request_verb = re.search(
        r"\b(?:donne|envoie|fournis|partage|telecharge|j ai besoin|peux tu me fournir)\b",
        normalized_query,
    )
    weak_term = any(term in normalized_query for term in WEAK_DOCUMENT_TERMS)
    return bool(request_verb and weak_term)


def _is_explicit_template_request(query: str) -> bool:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return False
    return _contains_strong_document_request(normalized_query)


def _deterministic_detection(query: str, templates_dict: dict[str, str]) -> Optional[str]:
    normalized_query = normalize_text(query)
    best_name: Optional[str] = None
    best_score = 0.0

    for filename, description in templates_dict.items():
        filename_norm = normalize_text(filename)
        description_norm = normalize_text(description)
        candidate = f"{filename_norm} {description_norm}".strip()

        if filename_norm in normalized_query:
            return filename

        overlap_tokens = set(normalized_query.split()) & set(candidate.split())
        overlap_ratio = len(overlap_tokens) / max(1, len(set(filename_norm.split())))
        fuzzy_score = _fuzzy_ratio(normalized_query, candidate)
        score = 0.65 * fuzzy_score + 0.35 * overlap_ratio

        if score > best_score:
            best_score = score
            best_name = filename

    return best_name if best_score >= 0.48 else None


def _llm_detection(llm, query: str, templates_dict: dict[str, str]) -> Optional[str]:
    if llm is None:
        return None

    template_list = "\n".join([f"- {name}: {description}" for name, description in templates_dict.items()])
    prompt = f"""
Tu identifies un template demandé par l'utilisateur.

Règles:
- N'identifie un template QUE si la demande est explicitement documentaire (template/modèle/fichier/formulaire/télécharger).
- Si l'utilisateur pose une simple question juridique sur un sujet (ex: "à quoi sert un avenant"), réponds AUCUN.
- Si un template est identifié, renvoie exactement son nom de fichier.

Templates disponibles:
{template_list}

Demande: {query}

Réponds strictement en JSON valide:
{{"filename":"nom exact ou AUCUN","confidence":0.0}}
"""
    try:
        result = llm.invoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return None
        payload = json.loads(match.group(0))
        detected = str(payload.get("filename", "AUCUN")).strip().strip('"').strip("'")
        if detected in templates_dict:
            return detected
    except Exception:
        return None
    return None


def detect_requested_template(query: str, templates_dict: dict[str, str], llm=None) -> Optional[str]:
    """Detect a requested template with deterministic pass + LLM fallback."""

    if not _is_explicit_template_request(query):
        return None

    deterministic = _deterministic_detection(query, templates_dict)
    if deterministic:
        return deterministic
    return _llm_detection(llm=llm, query=query, templates_dict=templates_dict)


def detect_template_with_ai(llm, query: str, templates_dict) -> Optional[str]:
    """Backward-compatible alias used by legacy code."""

    return detect_requested_template(query=query, templates_dict=templates_dict, llm=llm)
