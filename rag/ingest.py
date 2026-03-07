"""Document ingestion pipeline into Chroma with correction helpers."""

from __future__ import annotations

import os
import sys
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from .config import get_embeddings, get_settings, get_vector_store
from .loader import process_documents


def ingest_folder(folder_path: str) -> int:
    """Load, chunk, and index a documentation folder."""

    if not os.path.exists(folder_path):
        print(f"Erreur: dossier introuvable: {folder_path}", file=sys.stderr)
        return 2

    docs = process_documents(folder_path)
    if not docs:
        print("Aucun document trouvé à indexer.")
        return 0

    try:
        vector_store = get_vector_store()
        vector_store.add_documents(docs)
        print(f"Indexation OK: {len(docs)} chunks ajoutés")
        return 0
    except Exception as exc:
        print(f"Erreur d'indexation Chroma: {exc}", file=sys.stderr)
        return 1


def get_all_corrections() -> list[dict[str, Any]]:
    """Return all admin corrections currently stored in Chroma."""

    settings = get_settings()
    db = Chroma(persist_directory=settings.chroma_path, embedding_function=get_embeddings())
    data = db.get(where={"type": "admin_correction"})

    items: list[dict[str, Any]] = []
    ids = data.get("ids", []) if data else []
    metadatas = data.get("metadatas", []) if data else []
    documents = data.get("documents", []) if data else []

    for index, item_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
        content = documents[index] if index < len(documents) else ""
        items.append(
            {
                "id": item_id,
                "content": content,
                "admin_id": metadata.get("admin_id", "unknown"),
                "discussion_id": metadata.get("discussion_id", ""),
                "context_question": metadata.get("context_question", ""),
                "created_at": metadata.get("created_at", ""),
                "priority": metadata.get("priority", "high"),
            }
        )

    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)

def add_correction_to_chroma(
    correction_text: str,
    context_question: str = "",
    admin_id: str = "",
    discussion_id: str = ""
) -> str:
    """
    Ajoute une correction admin dans ChromaDB avec métadonnées prioritaires.
    """

    try:
        from datetime import datetime

        vector_store = get_vector_store()

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_admin_id = admin_id or "unknown_admin"
        correction_id = f"correction_{safe_admin_id}_{timestamp}"

        correction_doc = Document(
            page_content=correction_text.strip(),
            metadata={
                "type": "admin_correction",
                "priority": "high",
                "admin_id": admin_id,
                "discussion_id": discussion_id,
                "context_question": context_question,
                "created_at": timestamp,
                "source": "admin_correction",
                "doc_type": "admin_correction",
                "topic": "admin_correction",
            }
        )

        vector_store.add_documents(
            documents=[correction_doc],
            ids=[correction_id],
        )

        return correction_id

    except Exception as e:
        raise Exception(f"Erreur lors de l'ajout de la correction: {e}") from e

def delete_correction_from_chroma(correction_id: str) -> bool:
    """Delete an admin correction by id."""

    settings = get_settings()
    db = Chroma(persist_directory=settings.chroma_path, embedding_function=get_embeddings())
    db.delete(ids=[correction_id])
    return True


def main() -> int:
    """CLI entrypoint for ingestion."""

    base = os.path.dirname(__file__)
    default_data_path = os.getenv("DATA_PATH", os.path.join(base, "data", "data_complete"))
    return ingest_folder(default_data_path)


if __name__ == "__main__":
    raise SystemExit(main())
