from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from typing import List, Dict, Any, Tuple
import os
from dotenv import load_dotenv
load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2, google_api_key=os.getenv("GOOGLE_API_KEY"))

embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

# Chemin de la base de données Chroma adapté pour Docker et développement local
chroma_db_path = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))


vector_store = Chroma(persist_directory=chroma_db_path, embedding_function=embeddings)
retriever = vector_store.as_retriever(search_kwargs={"k": 5})

custom_prompt = PromptTemplate.from_template("""
Tu t'appelles Badinter. Tu es un assistant juridique spécialisé dans le cadre légal des Junior Entreprises françaises. Utilise les informations suivantes pour répondre à la question de manière factuelle et concise. Ne mentionne pas ce que je viens de te dire et n'utilise pas de caractères comme des * dans ta réponse.

Historique de la conversation :
{conversation_history}

Contexte documentaire :
{context}

Question actuelle :
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

def format_conversation_history(messages: List[Dict[str, Any]]) -> str:
    """
    Formate l'historique de conversation pour le prompt
    """
    if not messages:
        return "Aucun historique de conversation."
    
    formatted_history = []
    for message in messages:
        role = message.get('role', 'user')
        content = message.get('content', '')
        
        if role == 'user':
            formatted_history.append(f"Utilisateur: {content}")
        elif role == 'bot':
            formatted_history.append(f"Badinter: {content}")
    
    return "\n".join(formatted_history)

def generate_answer(query: str, conversation_history: List[Dict[str, Any]] = None) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Génère une réponse en prenant en compte l'historique de conversation
    """
    if conversation_history is None:
        conversation_history = []

    formatted_history = format_conversation_history(conversation_history)
    
    context_docs = retriever.get_relevant_documents(query)
    context = "\n".join([doc.page_content for doc in context_docs])
    
    full_prompt = custom_prompt.format(
        conversation_history=formatted_history,
        context=context,
        question=query
    )
    
    response = llm.invoke(full_prompt)
    answer = response.content if hasattr(response, 'content') else str(response)
    
    sources = [(doc.metadata.get('source'), doc.metadata.get('page')) for doc in context_docs]
    
    print(f"Réponse : {answer}")
    return answer, sources