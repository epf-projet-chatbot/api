"""Main RAG service pipeline for legal assistant generation."""

from __future__ import annotations

import re
from typing import Any, Optional

from .config import get_llm
from .detector import detect_requested_template
from .models import AnswerResult, QueryAnalysis, TaskType
from .prompts import QUIZ_VALIDATION_PROMPT, get_prompt_for_task
from .query_analyzer import analyze_query
from .reranker import rerank_documents
from .retrieval import has_sufficient_context, retrieve_context
from .templates import AVAILABLE_TEMPLATES, get_template_path
from .utils import clean_final_answer, ensure_sources_section, format_conversation_history


def _render_prompt(
    task_type: TaskType,
    query: str,
    history: str,
    context_text: str,
    analysis: QueryAnalysis,
    template_name: str = "",
) -> str:
    prompt_template = get_prompt_for_task(task_type)
    return prompt_template.format(
        query=query,
        conversation_history=history,
        context=context_text,
        mcq_options="\n".join(f"- {opt}" for opt in analysis.mcq_options) if analysis.mcq_options else "",
        template_name=template_name,
    )


def _safe_llm_invoke(prompt: str, system_prompt: str | None = None) -> str:
    llm = get_llm()
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    try:
        response = llm.invoke(full_prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        return "Je rencontre une indisponibilité temporaire du modèle. Merci de réessayer dans un instant."


def _validate_generated_quiz(answer: str, context_text: str) -> str:
    """Second-pass validation for generated quizzes."""

    prompt = QUIZ_VALIDATION_PROMPT.format(context=context_text, quiz_answer=answer)
    validated = _safe_llm_invoke(prompt)
    content = (validated or "").strip()
    if content.upper() == "OK":
        return answer
    return content or answer


def _build_prudent_answer(query: str, source_blocks: list[dict[str, str]]) -> str:
    """Safe response when context quality is insufficient."""

    base = (
        "# Réponse insuffisamment étayée\n\n"
        "Je ne trouve pas, dans les documents disponibles, suffisamment d'éléments fiables pour répondre précisément à cette question.\n\n"
        "## Ce qui manque\n"
        "- Le contexte récupéré ne permet pas de confirmer la réponse avec un niveau de fiabilité suffisant.\n\n"
        "## Recommandation\n"
        "- Reformuler la question en précisant le document, la procédure ou le cas concerné.\n"
        "- Vérifier s'il existe un document source plus spécifique sur ce sujet.\n\n"
        "Pour toute demande, n'hésitez pas à contacter Quentin Dufour, aussi appelé @dieu sur Slack.\n"
    )
    return ensure_sources_section(base, source_blocks)


def _append_admin_note_if_needed(answer: str, used_admin_corrections: bool) -> str:
    if not used_admin_corrections:
        return answer
    note = "\n\nℹ️ Cette réponse inclut une correction validée par un administrateur."
    return answer if note.strip() in answer else f"{answer}{note}"


def _extract_template_signal(answer: str) -> str:
    return re.sub(r"TEMPLATE_REQUEST:\s*.+?(?:\n|$)", "", answer, flags=re.IGNORECASE).strip()


def _to_result(
    answer: str,
    sources: list[tuple[str, str]],
    template_path: Optional[str],
    analysis: QueryAnalysis,
    confidence_score: float,
) -> AnswerResult:
    return AnswerResult(
        answer=answer,
        sources=sources,
        template_path=template_path,
        task_type=analysis.task_type,
        confidence_score=confidence_score,
    )


def generate_answer(
    query: str,
    conversation_history: list[dict[str, Any]] | None = None,
    system_prompt: str | None = None,
) -> tuple[str, list[tuple[str, str]], str | None]:
    """Main generation entrypoint used by API routes.

    Pipeline:
    1) query analysis
    2) optional template detection
    3) retrieval main docs + admin corrections
    4) reranking
    5) confidence/context sufficiency checks
    6) prompt selection
    7) generation
    8) post-processing and citations
    """

    # Routing is heuristic-first with LLM fallback; keep this object for debugability.
    analysis = analyze_query(query, llm=get_llm())
    history = format_conversation_history(conversation_history)

    template_path: str | None = None
    template_name: str = ""

    if analysis.task_type == TaskType.TEMPLATE_REQUEST:
        detected = detect_requested_template(query, AVAILABLE_TEMPLATES, llm=get_llm())
        if detected:
            template_name = detected
            template_path = get_template_path(detected)
        elif analysis.confidence_score < 0.80:
            # Weak template intent without concrete detected document:
            # fall back to OPEN_QA to avoid over-triggering template mode.
            analysis = QueryAnalysis(
                task_type=TaskType.OPEN_QA,
                normalized_query=analysis.normalized_query,
                confidence_score=analysis.confidence_score,
                mcq_options=analysis.mcq_options,
                rationale=f"{analysis.rationale} | Aucun template détecté, fallback OPEN_QA.",
            )

    retrieved = retrieve_context(query=query, task_type=analysis.task_type)
    if retrieved.docs:
        retrieved.docs = rerank_documents(query=query, docs=retrieved.docs, llm=get_llm())

    if not has_sufficient_context(analysis.task_type, retrieved):
        prudent = _build_prudent_answer(query, retrieved.source_blocks)
        prudent = _append_admin_note_if_needed(prudent, retrieved.used_admin_corrections)
        result = _to_result(prudent, retrieved.sources, template_path, analysis, retrieved.confidence_score)
        return result.answer, result.sources, result.template_path

    prompt = _render_prompt(
        task_type=analysis.task_type,
        query=query,
        history=history,
        context_text=retrieved.context_text,
        analysis=analysis,
        template_name=template_name,
    )

    answer = _safe_llm_invoke(prompt, system_prompt=system_prompt)
    if analysis.task_type == TaskType.QUIZ_GENERATION:
        answer = _validate_generated_quiz(answer, retrieved.context_text)

    answer = _extract_template_signal(answer)
    answer = clean_final_answer(answer)
    answer = ensure_sources_section(answer, retrieved.source_blocks)
    answer = _append_admin_note_if_needed(answer, retrieved.used_admin_corrections)

    result = _to_result(answer, retrieved.sources, template_path, analysis, retrieved.confidence_score)
    return result.answer, result.sources, result.template_path


def _manual_test() -> None:
    """Simple manual test runner for quick local checks."""

    samples = [
        "Quelle est la différence entre convention cadre et convention d'étude ?",
        "Parmi ces options, laquelle est correcte ?\nA) ...\nB) ...\nC) ...\nD) ...",
        "Génère un QCM sur les avenants",
        "Donne-moi le template de bon de commande",
    ]

    for sample in samples:
        print("\n" + "=" * 80)
        print("QUESTION:", sample)
        answer, sources, template = generate_answer(sample)
        print("TEMPLATE:", template)
        print("SOURCES:", sources[:3])
        print("ANSWER:\n", answer[:800], "..." if len(answer) > 800 else "")


if __name__ == "__main__":
    _manual_test()
