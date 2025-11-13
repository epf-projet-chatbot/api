from loader import process_documents
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

if __name__ == "__main__":
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