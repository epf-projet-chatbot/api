from langchain_chroma import Chroma
from langchain_core.documents import Document
import getpass
import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import time
import requests

# Load environment variables first
load_dotenv()

# Chemin de la base de données Chroma adapté pour être au même niveau qu'answer.py
CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialisation des embeddings
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)

def wait_for_api(url: str, timeout: int = 340):
    """Attend que l'API soit disponible"""
    for i in range(timeout):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise Exception("API timeout")




def embed(text: str) -> list[float]:
    """Vectorise un texte avec Google Generative AI"""
    try:
        return embeddings.embed_query(text)
    except Exception:
        return []

def add_to_chroma(chunks: list[Document]):
    """Ajoute des chunks à Chroma"""
    try:
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
        max_v1 = db._client.get_max_batch_size()
        
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
            chunk_id = f"{source}:{page}:{i}"
            
            counter = 0
            original_chunk_id = chunk_id
            while chunk_id in existing_ids or chunk_id in chunk_ids:
                counter += 1
                chunk_id = f"{original_chunk_id}_{counter}"
            
            chunk.metadata['id'] = chunk_id
            chunk_ids.append(chunk_id)
            existing_ids.add(chunk_id)
        
        for i in range(0, len(chunks), max_v1):
            batch_chunks = chunks[i:i + max_v1]
            batch_ids = chunk_ids[i:i + max_v1]
            db.add_documents(batch_chunks, ids=batch_ids)
            time.sleep(1)
        
    except Exception as e:
        raise Exception(f"Erreur Chroma: {e}")


async def add_correction_to_chroma(
    correction_text: str,
    context_question: str = "",
    admin_id: str = "",
    discussion_id: str = ""
) -> str:
    """
    ajoute une correction admin dans ChromaDB avec métadonnées prioritaires
    """
    try:
        from datetime import datetime
        
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
        
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
        
        db.add_documents([correction_doc], ids=[correction_id])

        return correction_id
        
    except Exception as e:
        raise Exception(f"Erreur lors de l'ajout de la correction: {e}")


def get_all_corrections() -> list[dict]:
    """
    Récupère toutes les corrections admin depuis ChromaDB
    """
    try:
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
        
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
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
        db.delete(ids=[correction_id])
        return True
        
    except Exception as e:
        raise Exception(f"Erreur lors de la suppression de la correction: {e}")

if __name__ == "__main__":
    # Import seulement pour l'embedding initial
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