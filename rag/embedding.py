from langchain_chroma import Chroma
from langchain_core.documents import Document
import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import time
import requests
from functools import lru_cache

load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "google").lower()
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/gemini-embedding-001")
GEMINI_EMBED_BATCH_SIZE = int(os.getenv("GEMINI_EMBED_BATCH_SIZE", "100"))

# Gemini embeddings (free-tier friendly settings)
embeddings = GoogleGenerativeAIEmbeddings(
    model=GEMINI_EMBED_MODEL,
    google_api_key=GOOGLE_API_KEY,
    batch_size=GEMINI_EMBED_BATCH_SIZE,
)

_vector_store = None


def get_vector_store() -> Chroma:
    global _vector_store
    if _vector_store is None:
        _vector_store = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
    return _vector_store

def wait_for_api(url: str, timeout: int = 340):
    for i in range(timeout):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise Exception("API timeout")


@lru_cache(maxsize=512)
def embed(text: str) -> list[float]:
    try:
        return embeddings.embed_query(text)
    except Exception as e:
        raise e

def add_to_chroma(chunks: list[Document]):
    try:
        db = get_vector_store()

        default_batch_size = "5" if EMBEDDING_PROVIDER == "google" else "64"
        BATCH_SIZE = int(os.getenv("CHROMA_BATCH_SIZE", default_batch_size))
        SLEEP_ON_429 = int(os.getenv("SLEEP_ON_429_SECONDS", "65"))
        SLEEP_BETWEEN_BATCHES = float(os.getenv("SLEEP_BETWEEN_BATCHES", "0.2"))

        max_v1 = db._client.get_max_batch_size()
        batch_size = min(BATCH_SIZE, max_v1)
        if batch_size <= 0:
            raise Exception(f"Invalid batch_size: {batch_size}")

        chunk_ids = []

        for i, chunk in enumerate(chunks):
            source = chunk.metadata.get('source', 'unknown')
            page = chunk.metadata.get('page', 0)
            chunk_id = f"{source}:{page}:{i}"

            chunk.metadata['id'] = chunk_id
            chunk_ids.append(chunk_id)

        total = len(chunks)
        total_batches = (total + batch_size - 1) // batch_size
        print(f"⚙️ Chroma max batch: {max_v1} | Using batch_size: {batch_size} | Total batches: {total_batches}")

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_ids = chunk_ids[i:i + batch_size]
            batch_num = (i // batch_size) + 1

            while True:
                try:
                    db.add_documents(batch_chunks, ids=batch_ids)
                    print(f"✅ Batch {batch_num}/{total_batches} indexed ({min(i+batch_size, total)}/{total})")
                    break
                except Exception as e:
                    msg = str(e)
                    if "existing id" in msg.lower() or "already exists" in msg.lower() or "duplicate" in msg.lower():
                        db.delete(ids=batch_ids)
                        db.add_documents(batch_chunks, ids=batch_ids)
                        print(f"♻️ Batch {batch_num}/{total_batches} overwritten ({min(i+batch_size, total)}/{total})")
                        break
                    if "429" in msg or "ResourceExhausted" in msg or "quota" in msg.lower():
                        print(f"⏳ 429 quota → sleeping {SLEEP_ON_429}s then retry (batch {batch_num}/{total_batches})")
                        time.sleep(SLEEP_ON_429)
                        continue
                    raise

            time.sleep(SLEEP_BETWEEN_BATCHES)

    except Exception as e:
        raise Exception(f"Erreur Chroma: {e}")


async def add_correction_to_chroma(
    correction_text: str,
    context_question: str = "",
    admin_id: str = "",
    discussion_id: str = ""
) -> str:
    try:
        from datetime import datetime

        SLEEP_ON_429 = int(os.getenv("SLEEP_ON_429_SECONDS", "65"))

        db = get_vector_store()

        timestamp = datetime.now().isoformat()
        correction_id = f"correction_{admin_id}_{discussion_id}_{timestamp}"

        full_content = f"CORRECTION PRIORITAIRE:\n{correction_text}"
        if context_question:
            full_content = f"Question: {context_question}\n\n{full_content}"

        correction_doc = Document(
            page_content=full_content,
            metadata={
                "id": correction_id,
                "type": "admin_correction",
                "priority": "high",
                "admin_id": admin_id,
                "discussion_id": discussion_id,
                "context_question": context_question,
                "created_at": timestamp,
                "source": "admin_correction"
            }
        )

        while True:
            try:
                db.add_documents([correction_doc], ids=[correction_id])
                return correction_id
            except Exception as e:
                msg = str(e)
                if "429" in msg or "ResourceExhausted" in msg or "quota" in msg.lower():
                    time.sleep(SLEEP_ON_429)
                    continue
                raise

    except Exception as e:
        raise Exception(f"Erreur lors de l'ajout de la correction: {e}")


def get_all_corrections() -> list[dict]:
    try:
        db = get_vector_store()

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
    try:
        db = get_vector_store()
        db.delete(ids=[correction_id])
        return True

    except Exception as e:
        raise Exception(f"Erreur lors de la suppression de la correction: {e}")


if __name__ == "__main__":
    from loader import process_documents

    print("🔍 Starting embedding process...")
    print("⏳ Waiting for API to be ready...")
    wait_for_api("http://api:8000/api/health")
    print("✅ API is ready!")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "data", "data_complete")

    print(f"📁 Looking for data in: {data_path}")

    if not os.path.exists(data_path):
        print(f"❌ ERROR: Data path does not exist: {data_path}")
        exit(1)

    print(f"✅ Data path exists!")
    print(f"📄 Processing documents from {data_path}...")

    documents = process_documents(data_path)

    if documents:
        print(f"✅ Found {len(documents)} documents")
        print(f"🔄 Adding documents to ChromaDB...")
        add_to_chroma(documents)
        print(f"✅ Embedding completed successfully! {len(documents)} documents added to ChromaDB")
    else:
        print(f"⚠️  No documents found to process")

    print("🎉 Embedding process finished!")