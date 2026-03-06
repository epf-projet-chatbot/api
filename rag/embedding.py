import os
import sys
from typing import List

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from rag.loader import process_documents

load_dotenv()

# Config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_PATH = os.path.join(SCRIPT_DIR, "data", "data_complete")

CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(SCRIPT_DIR, "chroma_db"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:4b")

# Paramètres de chunking
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

def get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )


def add_to_chroma(docs: List[Document]) -> bool:
    """Ajoute les documents à ChromaDB de manière simple"""
    print(f"Initialisation Ollama embeddings: {OLLAMA_EMBED_MODEL} ({OLLAMA_BASE_URL})")
    embeddings = get_embeddings()
    print(f"Modèle d'embedding prêt : {OLLAMA_EMBED_MODEL}")

    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    if not docs:
        print("Aucun chunk valide à indexer.")
        return True

    print(f"Indexation de {len(docs)} chunks...")
    
    try:
        db.add_documents(docs)
        print(f"✓ {len(docs)} chunks ajoutés avec succès")
        return True
    except Exception as e:
        print(f"✗ Erreur lors de l'ajout des documents: {e}")
        return False


def get_all_corrections() -> list[dict]:
    """
    Récupère toutes les corrections admin depuis ChromaDB
    """
    try:
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
        
        all_data = db.get(
            where={"type": "admin_correction"}
        )
        
        corrections = []
        if all_data and 'ids' in all_data:
            for i, doc_id in enumerate(all_data['ids']):
                metadata = all_data['metadatas'][i] if 'metadatas' in all_data and i < len(all_data['metadatas']) else {}
                content = all_data['documents'][i] if 'documents' in all_data and i < len(all_data['documents']) else ""
                
                corrections.append({
                    "id": doc_id,
                    "content": content,
                    "admin_id": metadata.get("admin_id", "unknown"),
                    "discussion_id": metadata.get("discussion_id", ""),
                    "context_question": metadata.get("context_question", ""),
                    "created_at": metadata.get("created_at", ""),
                    "priority": metadata.get("priority", "high")
                })
        
        return sorted(corrections, key=lambda x: x.get("created_at", ""), reverse=True)
        
    except Exception as e:
        raise Exception(f"Erreur lors de la récupération des corrections: {e}")


def delete_correction_from_chroma(correction_id: str) -> bool:
    """
    Supprime une correction de ChromaDB
    """
    try:
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
        db.delete(ids=[correction_id])
        return True
        
    except Exception as e:
        raise Exception(f"Erreur lors de la suppression de la correction: {e}")

def main() -> int:
    """Point d'entrée pour l'indexation des documents"""
    data_path = os.getenv("DATA_PATH", DEFAULT_DATA_PATH)
    if not os.path.exists(data_path):
        print(f"Erreur : Le répertoire {data_path} n'existe pas.", file=sys.stderr)
        return 2

    print(f"Traitement des documents de {data_path}")
    print(f"Paramètres de chunking: chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP}")
    
    # Utilise les paramètres de chunking du loader
    docs = process_documents(
        folder_path=data_path,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        lemmatize=False
    )
    
    if not docs:
        print("Aucun document trouvé à traiter.")
        return 0

    ok = add_to_chroma(docs)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
