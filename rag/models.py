"""Data models and enums for the RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from langchain_core.documents import Document


class TaskType(str, Enum):
    """Supported high-level tasks for the legal assistant."""

    OPEN_QA = "open_qa"
    MCQ_ANSWERING = "mcq_answering"
    QUIZ_GENERATION = "quiz_generation"
    TEMPLATE_REQUEST = "template_request"


@dataclass(slots=True)
class QueryAnalysis:
    """Result of query understanding and routing."""

    task_type: TaskType
    normalized_query: str
    confidence_score: float
    mcq_options: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(slots=True)
class RetrievedContext:
    """Structured retrieval output consumed by generation."""

    docs: list[Document]
    context_text: str
    sources: list[tuple[str, str]]
    source_blocks: list[dict[str, Any]]
    used_admin_corrections: bool
    confidence_score: float
    relevant_count: int


@dataclass(slots=True)
class AnswerResult:
    """Final pipeline output."""

    answer: str
    sources: list[tuple[str, str]]
    template_path: Optional[str]
    task_type: TaskType
    confidence_score: float
