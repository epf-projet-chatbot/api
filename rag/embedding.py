from loader import process_documents
from langchain_chroma import Chroma
from langchain_core.documents import Document
import os
import re
import time
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Load environment variables first
load_dotenv()

# Chemin de la base de données Chroma adapté pour être au même niveau qu'answer.py
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMBEDDING_MODEL = os.getenv("GOOGLE_EMBEDDING_MODEL")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "20"))
EMBEDDING_MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "8"))
EMBEDDING_MIN_INTERVAL_SECONDS = float(os.getenv("EMBEDDING_MIN_INTERVAL_SECONDS", "0.8"))


class RateLimitedEmbeddings:
    def __init__(
        self,
        base_embeddings: GoogleGenerativeAIEmbeddings,
        batch_size: int = 20,
        max_retries: int = 8,
        min_interval_seconds: float = 0.8,
    ) -> None:
        self.base_embeddings = base_embeddings
        self.batch_size = max(1, batch_size)
        self.max_retries = max(1, max_retries)
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self._last_request_time = 0.0

    def _wait_min_interval(self) -> None:
        elapsed = time.time() - self._last_request_time
        sleep_seconds = self.min_interval_seconds - elapsed
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    def _extract_retry_delay(self, error_message: str) -> float:
        match = re.search(r"Please retry in\s*([0-9]+(?:\.[0-9]+)?)ms", error_message)
        if not match:
            return 2.0
        milliseconds = float(match.group(1))
        return max(0.5, (milliseconds / 1000.0) + 0.2)

    def _is_quota_error(self, error_message: str) -> bool:
        lowered = error_message.lower()
        return "429" in lowered or "quota" in lowered or "rate" in lowered

    def _call_with_retries(self, texts: list[str]) -> list[list[float]]:
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            self._wait_min_interval()
            try:
                self._last_request_time = time.time()
                return self.base_embeddings.embed_documents(texts)
            except Exception as error:
                last_error = error
                message = str(error)
                if not self._is_quota_error(message):
                    raise
                delay = self._extract_retry_delay(message)
                print(
                    f"Quota embedding atteint (tentative {attempt}/{self.max_retries}). "
                    f"Nouvelle tentative dans {delay:.2f}s..."
                )
                time.sleep(delay)
        raise last_error

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        all_vectors = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            all_vectors.extend(self._call_with_retries(batch))
        return all_vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self._call_with_retries([text])
        return vectors[0]

def _init_embeddings() -> RateLimitedEmbeddings:
    model_candidates = []

    if EMBEDDING_MODEL:
        normalized_model = EMBEDDING_MODEL.strip()
        if normalized_model and not normalized_model.startswith("models/"):
            normalized_model = f"models/{normalized_model}"
        model_candidates.append(normalized_model)

    model_candidates.extend([
        "models/gemini-embedding-001",
        "models/embedding-001",
    ])

    seen = set()
    unique_candidates = []
    for model in model_candidates:
        if model not in seen:
            seen.add(model)
            unique_candidates.append(model)

    last_error = None
    for model in unique_candidates:
        try:
            base_embedding_client = GoogleGenerativeAIEmbeddings(model=model, google_api_key=GOOGLE_API_KEY)
            embedding_client = RateLimitedEmbeddings(
                base_embeddings=base_embedding_client,
                batch_size=EMBEDDING_BATCH_SIZE,
                max_retries=EMBEDDING_MAX_RETRIES,
                min_interval_seconds=EMBEDDING_MIN_INTERVAL_SECONDS,
            )
            embedding_client.embed_query("ping")
            print(f"Modèle d'embedding utilisé : {model}")
            return embedding_client
        except Exception as error:
            last_error = error
            print(f"Modèle d'embedding indisponible ({model}) : {error}")

    raise RuntimeError(
        "Aucun modèle d'embedding Gemini compatible n'a pu être initialisé. "
        "Vérifiez GOOGLE_API_KEY et GOOGLE_EMBEDDING_MODEL (ex: models/gemini-embedding-001)."
    ) from last_error

# Initialisation des embeddings
embeddings = _init_embeddings()

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
        max_batch_size = db._client.get_max_batch_size()
        # Obtenir les IDs existants pour éviter les doublons
        existing_ids = set()
        try:
            existing_collection = db.get()
            if existing_collection and 'ids' in existing_collection:
                existing_ids = set(existing_collection['ids'])
        except:
            pass
        
        chunk_ids = []
        
        for i, chunk in enumerate(chunks):
            source = chunk.metadata.get('source', 'unknown')
            page = chunk.metadata.get('page', 0)
            
            # Format: document_id:page_id:chunk_index
            chunk_id = f"{source}:{page}:{i}"
            
            # S'assurer qu'il n'y a pas de doublons
            counter = 0
            original_chunk_id = chunk_id
            while chunk_id in existing_ids or chunk_id in chunk_ids:
                counter += 1
                chunk_id = f"{original_chunk_id}_{counter}"
            
            chunk.metadata['id'] = chunk_id
            chunk_ids.append(chunk_id)
            existing_ids.add(chunk_id)
        
        # Ajouter les documents par paquets de taille max
        for i in range(0, len(chunks), max_batch_size):
            batch_chunks = chunks[i:i + max_batch_size]
            batch_ids = chunk_ids[i:i + max_batch_size]
            db.add_documents(batch_chunks, ids=batch_ids)
            print(f"{len(chunks)} chunks ajoutés à la base de données Chroma.")
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
