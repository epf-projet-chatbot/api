from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import os
from dotenv import load_dotenv
load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2, google_api_key=os.getenv("GOOGLE_API_KEY"))

# Même modèle d'embedding que dans embedding.py (via Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")
embeddings = OllamaEmbeddings(
    model=OLLAMA_EMBED_MODEL,
    base_url=OLLAMA_BASE_URL,
)

# Chemin de la base de données Chroma (priorité à l'env pour Docker/volume persistant)
chroma_db_path = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))

vector_store = Chroma(persist_directory=chroma_db_path, embedding_function=embeddings)
retriever = vector_store.as_retriever(search_kwargs={"k": 5})

custom_prompt = PromptTemplate.from_template("""
Tu t'appelles Badinter. Tu es un assistant juridique spécialisé dans le cadre légal des Junior Entreprises françaises. Utilise les informations suivantes pour répondre à la question de manière factuelle et concise. Ne mentionne pas ce que je viens de te dire et n'utilise pas de caractères comme des * dans ta réponse.

Contexte :
{context}

Question :
{question}

Réponse :
""")

rag_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True,
    chain_type_kwargs={"prompt": custom_prompt}
)

""" query = input("Posez votre question juridique sur les Junior Entreprises : ")
result = rag_chain.invoke({"query": query})

print("Réponse :", result["result"])
for doc in result["source_documents"]:
    print(f"Source: {doc.metadata.get('source')}, page: {doc.metadata.get('page')}") """

def generate_answer(query):
    result = rag_chain.invoke({"query": query})
    answer = result["result"]
    sources = [(doc.metadata.get('source'), doc.metadata.get('page')) for doc in result["source_documents"]]
    print(f"Réponse : {answer}")
    return answer, sources