from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from typing import List, Dict, Any, Tuple, Optional
import os
import re
from dotenv import load_dotenv
load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2, google_api_key=os.getenv("GOOGLE_API_KEY"))

embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

# Chemin de la base de données Chroma adapté pour Docker 
chroma_db_path = os.getenv("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "chroma_db"))
data_complete_path = os.path.join(os.path.dirname(__file__), "data", "data_complete")

vector_store = Chroma(persist_directory=chroma_db_path, embedding_function=embeddings)
retriever = vector_store.as_retriever(search_kwargs={"k": 5})

# TODO: Rajouter les prochains templates (s'il y en a), et adapter l'ordre hiérarchique
# Mapping des templates disponibles (il comprends mieux avec cet ordre hiérarchique, moins de problèmes)
AVAILABLE_TEMPLATES = {
    # Templates de conventions
    "convention d'étude": "Convention d'Etude - AGP_CRP_25.pdf",
    "convention d'études": "Convention d'Etude - AGP_CRP_25.pdf",
    "convention etude": "Convention d'Etude - AGP_CRP_25.pdf",
    "convention cadre": "Convention Cadre - AGP_CRP_25.pdf",
    "convention pro-bono": "Convention d'Etude Pro-Bono - AGP_Sept_24 - V0 2024.06.14.pdf",
    "convention pro bono": "Convention d'Etude Pro-Bono - AGP_Sept_24 - V0 2024.06.14.pdf",
    
    # Templates d'avenants 
    "avenant de rupture convention": "Avenant-de-Rupture-à-la-Convention-dEtude.pdf",
    "avenant de rupture": "Avenant-de-Rupture-à-la-Convention-dEtude.pdf",
    "avenant rupture": "Avenant-de-Rupture-à-la-Convention-dEtude.pdf",
    "avenant par mail": "Avenant par mail à la Convention d'Etude - AGP_CRP_25.pdf",
    "avenant à la convention d'étude": "Avenant à la Convention d'Etude - AGP_CRP_25.pdf",
    "avenant à la convention": "Avenant à la Convention d'Etude - AGP_CRP_25.pdf",
    "avenant convention": "Avenant à la Convention d'Etude - AGP_CRP_25.pdf",
    "avenant à la convention cadre": "Avenant-a-la-Convention-Cadre-1.pdf",
    "avenant": "Avenant à la Convention d'Etude - AGP_CRP_25.pdf",
    
    # Templates de bons de commande
    "bon de commande rectificatif": "Bon de Commande Rectificatif - AGP_CRP_25.pdf",
    "bon de commande": "Bon de Commande - AGP_CRP_25.pdf",
    
    # Templates de procès-verbal
    "procès-verbal de recette": "Procès-Verbal de Recette Finale - AGP_CRP_25.pdf",
    "pv de recette": "Procès-Verbal de Recette Finale - AGP_CRP_25.pdf",
    "recette finale": "Procès-Verbal de Recette Finale - AGP_CRP_25.pdf",
}

custom_prompt = PromptTemplate.from_template("""
Tu t'appelles Badinter. Tu es l'assistant juridique de la junior entreprise EPF Projets, spécialisé dans le cadre légal des Junior Entreprises. Utilise les informations suivantes pour répondre à la question de manière factuelle et concise. Ne mentionne pas ce que je viens de te dire et n'utilise pas de caractères comme des * dans ta réponse.

RÈGLE ABSOLUE POUR LES TEMPLATES : 
Si l'utilisateur demande un template, un modèle, un document, un fichier ou un avenant, tu DOIS OBLIGATOIREMENT :
1. Répondre normalement à sa question
2. Ajouter UNE NOUVELLE LIGNE à la fin
3. Écrire exactement "TEMPLATE_REQUEST:" suivi du type de document demandé

Documents disponibles et leurs identifiants :
- Convention d'étude → "TEMPLATE_REQUEST: convention d'étude"
- Convention cadre → "TEMPLATE_REQUEST: convention cadre"
- Avenant à convention → "TEMPLATE_REQUEST: avenant"
- Avenant de rupture → "TEMPLATE_REQUEST: avenant de rupture"
- Avenant par mail → "TEMPLATE_REQUEST: avenant par mail"
- Bon de commande → "TEMPLATE_REQUEST: bon de commande"
- PV de recette → "TEMPLATE_REQUEST: procès-verbal de recette"

EXEMPLES :
Question : "Peux-tu me donner un template d'avenant ?"
Réponse : "Oui, je peux vous fournir un modèle d'avenant à une convention d'étude.
TEMPLATE_REQUEST: avenant"

Question : "J'ai besoin d'une convention d'étude"
Réponse : "Voici les informations sur la convention d'étude.
TEMPLATE_REQUEST: convention d'étude"

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

def format_conversation_history(messages: List[Dict[str, Any]]) -> str:
    """Formate l'historique de conversation"""
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

def detect_template_request(text: str) -> Optional[str]:
    """
    Détecte si le texte contient une demande de template
    Retourne le chemin du fichier template si détecté, None sinon
    """
    text_lower = text.lower()
    
    # Chercher le pattern TEMPLATE_REQUEST dans la réponse de l'IA
    template_pattern = r"TEMPLATE_REQUEST:\s*(.+?)(?:\n|$)"
    match = re.search(template_pattern, text, re.IGNORECASE)
    
    if match:
        requested_template = match.group(1).strip().lower()
        
        # Chercher le meilleur match dans le mapping des templates
        best_match = None
        best_match_length = 0
        
        for key, filename in AVAILABLE_TEMPLATES.items():
            if key in requested_template or requested_template in key:
                # Prendre le match le plus long (plus précis)
                if len(key) > best_match_length:
                    template_path = os.path.join(data_complete_path, filename)
                    if os.path.exists(template_path):
                        best_match = template_path
                        best_match_length = len(key)
        
        if best_match:
            return best_match
    
    # Petit fallback au cas où
    template_keywords = ["template", "modèle", "document", "fichier", "pdf", "convention", "avenant", "transmettre", "filer", "envoyer"]
    
    if any(keyword in text_lower for keyword in template_keywords):
        # Chercher le meilleur match (le plus long =le plus spécifique)
        best_match = None
        best_match_length = 0
        
        for key, filename in AVAILABLE_TEMPLATES.items():
            if key in text_lower:
                # Prendre le match le plus long 
                if len(key) > best_match_length:
                    template_path = os.path.join(data_complete_path, filename)
                    if os.path.exists(template_path):
                        best_match = template_path
                        best_match_length = len(key)
        
        if best_match:
            return best_match
    
    return None

def generate_answer(query: str, conversation_history: List[Dict[str, Any]] = None) -> Tuple[str, List[Tuple[str, str]], Optional[str]]:
    """
    Génère une réponse avec historique
    Retourne : (answer, sources, template_path)
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
    
    # On détecte si un template est demandé
    template_path = detect_template_request(answer)
    
    # Si template détecté dans la réponse de l'IA, vérifier aussi dans la query originale
    if not template_path:
        template_path = detect_template_request(query)
    
    # Nettoyer la réponse du marqueur TEMPLATE_REQUEST
    answer = re.sub(r"TEMPLATE_REQUEST:\s*.+?(?:\n|$)", "", answer, flags=re.IGNORECASE).strip()
    
    return answer, sources, template_path