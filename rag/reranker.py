"""Pluggable reranking module for retrieved documents."""

from __future__ import annotations

from typing import Protocol

from langchain_core.documents import Document

from .utils import normalize_text


class Reranker(Protocol):
    """Protocol for swappable reranker implementations."""

    def rank(self, query: str, docs: list[Document], llm=None) -> list[Document]:
        """Return documents sorted by relevance."""


class HeuristicReranker:
    """Baseline reranker using retrieval score + lexical overlap.

    Extension point:
    - Replace this class with a cross-encoder reranker for stronger semantic ranking.
    - Add offline evaluation hooks to compare ranking quality over curated QA sets.
    """

    def rank(self, query: str, docs: list[Document], llm=None) -> list[Document]:
        if not docs:
            return []

        query_terms = set(normalize_text(query).split())

        def score(doc: Document) -> float:
            retrieval_conf = float(doc.metadata.get("confidence_score", 0.0))
            content_terms = set(normalize_text(doc.page_content).split())
            overlap = len(query_terms & content_terms) / max(1, len(query_terms))
            return 0.7 * retrieval_conf + 0.3 * overlap

        ranked = sorted(docs, key=score, reverse=True)
        return ranked


def rerank_documents(query: str, docs: list[Document], llm=None, reranker: Reranker | None = None) -> list[Document]:
    """Rerank documents with default heuristic strategy.

    Extension point:
    - Inject a stronger reranker instance implementing `Reranker`.
    """

    active_reranker = reranker or HeuristicReranker()
    return active_reranker.rank(query=query, docs=docs, llm=llm)
