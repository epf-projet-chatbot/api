"""Retrieval layer for main docs + prioritized admin corrections."""

from __future__ import annotations

import math
from typing import Any

from langchain_core.documents import Document

from .config import get_settings, get_vector_store
from .models import RetrievedContext, TaskType


def retrieve_admin_corrections(query: str, vector_store=None) -> list[tuple[Document, float]]:
    """Retrieve high-priority admin corrections relevant to a query."""

    settings = get_settings()
    vs = vector_store or get_vector_store()
    try:
        results = vs.similarity_search_with_score(
            query,
            k=settings.admin_corrections_k,
            filter={
                "$and": [
                    {"type": {"$eq": "admin_correction"}},
                    {"priority": {"$eq": "high"}},
                ]
            },
        )
        return results
    except Exception:
        return []


def retrieve_main_documents(query: str, vector_store=None, k: int | None = None) -> list[tuple[Document, float]]:
    """Retrieve standard knowledge chunks from Chroma."""

    settings = get_settings()
    vs = vector_store or get_vector_store()
    size = k or settings.retrieval_k
    fetch_size = max(size, settings.retrieval_fetch_k)
    try:
        results = vs.similarity_search_with_score(query, k=fetch_size)
        return results
    except Exception:
        return []


def _score_to_confidence(score: float) -> float:
    """Convert distance-like score into confidence in [0,1]."""

    s = max(0.0, float(score))
    value = math.exp(-s)
    return max(0.0, min(value, 1.0))


def filter_by_relevance(items: list[tuple[Document, float]], threshold: float) -> list[tuple[Document, float]]:
    """Keep documents below the distance threshold (Chroma-style score)."""

    filtered = [(doc, score) for doc, score in items if float(score) <= threshold]
    return filtered


def _enrich_metadata(doc: Document, score: float) -> Document:
    meta = dict(doc.metadata or {})
    meta.setdefault("source", "source inconnue")
    meta.setdefault("page", "?")
    meta.setdefault("section", "")
    meta.setdefault("doc_type", "unknown")
    meta.setdefault("topic", "general")
    meta["retrieval_score"] = float(score)
    meta["confidence_score"] = _score_to_confidence(score)
    return Document(page_content=doc.page_content, metadata=meta)


def build_context_blocks(docs: list[Document]) -> tuple[str, list[dict[str, str]]]:
    """Build context blocks and source metadata."""

    blocks: list[str] = []
    sources: list[dict[str, str]] = []
    for doc in docs:
        source = str(doc.metadata.get("source", "source inconnue"))
        page = str(doc.metadata.get("page", "?"))
        section = str(doc.metadata.get("section", ""))
        blocks.append(
            f"source={source} | page={page} | section={section}\n{doc.page_content}"
        )
        sources.append(
            {
                "source": source,
                "page": page,
                "section": section,
                "doc_type": str(doc.metadata.get("doc_type", "unknown")),
                "topic": str(doc.metadata.get("topic", "general")),
            }
        )
    return "\n\n".join(blocks), sources


def extract_sources(source_blocks: list[dict[str, str]]) -> list[tuple[str, str]]:
    """Extract API-compatible sources tuple list."""

    return [(block.get("source", "source inconnue"), block.get("page", "?")) for block in source_blocks]


def has_sufficient_context(task_type: TaskType, context: RetrievedContext) -> bool:
    """Determine if context quality is sufficient for a safe answer."""

    if context.relevant_count == 0:
        return False

    if task_type == TaskType.OPEN_QA:
        if context.used_admin_corrections and context.relevant_count >= 1:
            return True
        if context.relevant_count >= 2 and context.confidence_score >= 0.22:
            return True
        if context.relevant_count == 1 and context.confidence_score >= 0.45:
            return True
        return False

    return context.confidence_score >= 0.20


def retrieve_context(query: str, task_type: TaskType, vector_store=None) -> RetrievedContext:
    """Retrieve and merge prioritized corrections + regular docs."""

    settings = get_settings()
    vs = vector_store or get_vector_store()

    raw_admin = retrieve_admin_corrections(query, vector_store=vs)
    raw_main = retrieve_main_documents(query, vector_store=vs)

    admin_docs = filter_by_relevance(raw_admin, settings.score_threshold_admin)
    main_docs = filter_by_relevance(raw_main, settings.score_threshold_main)
    if len(main_docs) > settings.retrieval_k:
        main_docs = main_docs[: settings.retrieval_k]

    merged_docs: list[Document] = []
    for doc, score in [*admin_docs, *main_docs]:
        merged_docs.append(_enrich_metadata(doc, score))

    context_text, source_blocks = build_context_blocks(merged_docs)

    if merged_docs:
        confidence = sum(float(doc.metadata.get("confidence_score", 0.0)) for doc in merged_docs) / len(merged_docs)
    else:
        confidence = 0.0

    return RetrievedContext(
        docs=merged_docs,
        context_text=context_text,
        sources=extract_sources(source_blocks),
        source_blocks=source_blocks,
        used_admin_corrections=bool(admin_docs),
        confidence_score=confidence,
        relevant_count=len(merged_docs),
    )
