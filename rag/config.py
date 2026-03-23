"""Centralized runtime configuration and factories for RAG components."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_ollama import ChatOllama, OllamaEmbeddings

load_dotenv()


@dataclass(frozen=True, slots=True)
class RagSettings:
    """Environment-driven settings for retrieval and generation."""

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large")
    ollama_llm_model: str = os.getenv("OLLAMA_LLM_MODEL", "kimi-k2:1t-cloud")
    chroma_path: str = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))
    retrieval_k: int = int(os.getenv("RAG_RETRIEVAL_K", "8"))
    retrieval_fetch_k: int = int(os.getenv("RAG_RETRIEVAL_FETCH_K", "24"))
    admin_corrections_k: int = int(os.getenv("RAG_ADMIN_CORRECTIONS_K", "3"))
    score_threshold_main: float = float(os.getenv("RAG_SCORE_THRESHOLD_MAIN", "1.15"))
    score_threshold_admin: float = float(os.getenv("RAG_SCORE_THRESHOLD_ADMIN", "1.00"))


@lru_cache(maxsize=1)
def get_settings() -> RagSettings:
    """Return a singleton settings object."""

    return RagSettings()


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
    """Create and cache the LLM client."""

    settings = get_settings()
    return ChatOllama(
        model=settings.ollama_llm_model,
        base_url=settings.ollama_base_url,
        temperature=0.2,
    )


class MxbaiEmbeddings(OllamaEmbeddings):
    """OllamaEmbeddings with mxbai-embed-large query prefix for asymmetric retrieval."""

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(
            f"Represent this sentence for searching relevant passages: {text}"
        )


@lru_cache(maxsize=1)
def get_embeddings() -> MxbaiEmbeddings:
    """Create and cache embeddings (same model for ingestion and query time)."""

    settings = get_settings()
    return MxbaiEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    """Create and cache Chroma vector store with shared embeddings."""

    settings = get_settings()
    return Chroma(
        persist_directory=settings.chroma_path,
        embedding_function=get_embeddings(),
    )
