"""Centralized runtime configuration and factories for RAG components."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import OllamaEmbeddings

load_dotenv()


@dataclass(frozen=True, slots=True)
class RagSettings:
    """Environment-driven settings for retrieval and generation."""

    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:4b")
    chroma_path: str = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))
    retrieval_k: int = int(os.getenv("RAG_RETRIEVAL_K", "8"))
    retrieval_fetch_k: int = int(os.getenv("RAG_RETRIEVAL_FETCH_K", "24"))
    admin_corrections_k: int = int(os.getenv("RAG_ADMIN_CORRECTIONS_K", "3"))
    score_threshold_main: float = float(os.getenv("RAG_SCORE_THRESHOLD_MAIN", "1.15"))
    score_threshold_admin: float = float(os.getenv("RAG_SCORE_THRESHOLD_ADMIN", "1.00"))


@lru_cache(maxsize=1) # lru_cache it's used as a singleton (like in Java)
def get_settings() -> RagSettings:
    """Return a singleton settings object."""

    return RagSettings()


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    """Create and cache the Gemini LLM client."""

    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=0.2,
        google_api_key=settings.google_api_key,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> OllamaEmbeddings:
    """Create and cache embeddings (same model for ingestion and query time)."""

    settings = get_settings()
    return OllamaEmbeddings(
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
