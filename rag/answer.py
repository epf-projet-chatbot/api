from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from typing import List, Dict, Any, Tuple, Optional
import os
import re
from dotenv import load_dotenv

from .templates import AVAILABLE_TEMPLATES, data_complete_path, get_template_path
from .detector import detect_template_with_ai

load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2, google_api_key=os.getenv("GOOGLE_API_KEY"))
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

chroma_db_path = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))
vector_store = Chroma(persist_directory=chroma_db_path, embedding_function=embeddings)
retriever = vector_store.as_retriever(search_kwargs={"k": 5})

custom_prompt = PromptTemplate.from_template("""
Tu t'appelles Badinter. Tu es l'assistant juridique de la junior entreprise EPF Projets, spécialisé dans le cadre légal des Junior Entreprises. 
Réponds de façon factuelle et concise.

Historique : {conversation_history}
Contexte : {context}
Question : {question}
Réponse :
""")

def format_conversation_history(messages: List[Dict[str, Any]]) -> str:
    if not messages:
        return ""
    out = []
    for m in messages:
        role = m.get('role', 'user')
        content = m.get('content', '')
        out.append(("Utilisateur: " if role == 'user' else "Badinter: ") + content)
    return "\n".join(out)


def generate_answer(query: str, conversation_history: List[Dict[str, Any]] = None) -> Tuple[str, List[Tuple[str, str]], Optional[str]]:
    if conversation_history is None:
        conversation_history = []

    history = format_conversation_history(conversation_history)
    
    # Chercher dans TOUS les documents (pas de filtrage)
    context_docs = retriever.get_relevant_documents(query)
    context = "\n".join([d.page_content for d in context_docs])

    full_prompt = custom_prompt.format(conversation_history=history, context=context, question=query)
    response = llm.invoke(full_prompt)
    answer = response.content if hasattr(response, 'content') else str(response)
    sources = [(d.metadata.get('source'), d.metadata.get('page')) for d in context_docs]


    requested_template = detect_template_with_ai(llm, query, AVAILABLE_TEMPLATES)
    template_path = None
    
    if requested_template:
        template_path = get_template_path(requested_template)

    answer = re.sub(r"TEMPLATE_REQUEST:\s*.+?(?:\n|$)", "", answer, flags=re.IGNORECASE).strip()
    return answer, sources, template_path
