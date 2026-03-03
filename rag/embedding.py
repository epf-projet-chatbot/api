from loader import process_documents
from langchain_chroma import Chroma
from langchain_core.documents import Document
import os
import time
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings

# Load environment variables first
load_dotenv()

# Chemin de la base de données Chroma (priorité à l'env pour Docker/volume persistant)
CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))

# Embeddings via Ollama (modèle local déjà pull sur le VPS)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "4"))
EMBED_MAX_CHARS = int(os.getenv("EMBED_MAX_CHARS", "12000"))

print(f"Initialisation Ollama embeddings: {OLLAMA_EMBED_MODEL} ({OLLAMA_BASE_URL})")
embeddings = OllamaEmbeddings(
    model=OLLAMA_EMBED_MODEL,
    base_url=OLLAMA_BASE_URL,
)
print(f"Modèle d'embedding prêt : {OLLAMA_EMBED_MODEL}")

def embed(text: str) -> list[float]:
    """
    Vectorise un texte en utilisant Google Generative AI Embeddings.
    
    Args:
        text (str): Le texte à vectoriser.
        
    Returns:
        list[float]: Le vecteur d'embedding du texte.
    """
    try:
        # Utilisation de l'API LangChain pour générer l'embedding
        result = embeddings.embed_query(text)
        return result
    except Exception as e:
        print(f"Erreur lors de la vectorisation : {e}")
        return []

def add_to_chroma(chunks: list[Document]) -> bool:
    """
    Ajoute des chunks à la base de données Chroma.
    
    Args:
        chunks (list[Document]): Liste de documents à ajouter.
    """
    try:
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
        max_batch_size = max(1, min(db._client.get_max_batch_size(), EMBEDDING_BATCH_SIZE))
        print(f"Taille de batch embedding utilisée: {max_batch_size}")
        # Obtenir les IDs existants pour éviter les doublons
        existing_ids = set()
        try:
            existing_collection = db.get()
            if existing_collection and 'ids' in existing_collection:
                existing_ids = set(existing_collection['ids'])
        except:
            pass
        
        chunks_to_add = []
        chunk_ids = []
        
        for i, chunk in enumerate(chunks):
            source = chunk.metadata.get('source', 'unknown')
            page = chunk.metadata.get('page', 0)
            
            # Format: document_id:page_id:chunk_index
            chunk_id = f"{source}:{page}:{i}"

            if chunk_id in existing_ids:
                continue
            
            chunk.metadata['id'] = chunk_id
            chunks_to_add.append(chunk)
            chunk_ids.append(chunk_id)
            existing_ids.add(chunk_id)

        # Nettoyer/filtrer les chunks avant embedding pour éviter les erreurs Ollama (400/EOF)
        filtered_chunks = []
        filtered_ids = []
        skipped_empty = 0
        truncated_count = 0
        for chunk, chunk_id in zip(chunks_to_add, chunk_ids):
            text = (chunk.page_content or "").replace("\x00", "").strip()
            if not text:
                skipped_empty += 1
                continue
            if len(text) > EMBED_MAX_CHARS:
                text = text[:EMBED_MAX_CHARS]
                truncated_count += 1
            chunk.page_content = text
            filtered_chunks.append(chunk)
            filtered_ids.append(chunk_id)

        chunks_to_add = filtered_chunks
        chunk_ids = filtered_ids

        if not chunks_to_add:
            print("Aucun nouveau chunk à ajouter à Chroma (déjà indexé).")
            return True

        print(f"{len(chunks_to_add)} nouveaux chunks à ajouter sur {len(chunks)}.")
        print(f"Chunks filtrés: vides ignorés={skipped_empty}, tronqués={truncated_count}, max_chars={EMBED_MAX_CHARS}.")
        
        # Ajouter les documents par paquets de taille adaptative
        current_batch_size = max_batch_size
        index = 0
        while index < len(chunks_to_add):
            batch_chunks = chunks_to_add[index:index + current_batch_size]
            batch_ids = chunk_ids[index:index + current_batch_size]
            try:
                db.add_documents(batch_chunks, ids=batch_ids)
                index += len(batch_chunks)
                print(f"{len(batch_chunks)} chunks ajoutés à la base de données Chroma.")
            except Exception as e:
                message = str(e).lower()
                if ("signal: killed" in message or "status code: 500" in message or "runner process has terminated" in message) and current_batch_size > 1:
                    next_batch = max(1, current_batch_size // 2)
                    print(f"Batch trop grand ({current_batch_size}). Nouvelle tentative avec batch={next_batch}.")
                    current_batch_size = next_batch
                    time.sleep(1)
                    continue
                if batch_chunks and batch_ids:
                    bad = batch_chunks[0]
                    bad_id = batch_ids[0]
                    text = bad.page_content or ""
                    print("---- EMBEDDING FAILED ----")
                    print(f"id={bad_id}")
                    print(f"len_chars={len(text)}")
                    print(f"start={repr(text[:200])}")
                    print(f"end={repr(text[-200:])}")
                    print("--------------------------")
                print(f"Échec sur un batch de taille {current_batch_size}: {e}")
                return False
        return True
        
    except Exception as e:
        print(f"Erreur lors de l'ajout à Chroma : {e}")
        return False

if __name__ == "__main__":
    """
    Point d'entrée pour le script.
    Charge les documents, les prétraite, les vectorise et les ajoute à la base de données Chroma.
    """
    
    # Chargement et ajout des documents
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "data", "data_complete")
    if not os.path.exists(data_path):
        print(f"Erreur : Le répertoire {data_path} n'existe pas.")
        exit(1)
    
    documents = process_documents(data_path)
    if documents:
        if add_to_chroma(documents):
            print("Chroma DB mise à jour avec succès.")
        else:
            print("Échec de la mise à jour de Chroma DB.")
    else:
        print("Aucun document trouvé à traiter.")