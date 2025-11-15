from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
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

** CORRECTIONS PRIORITAIRES **
Si le contexte contient des "CORRECTIONS PRIORITAIRES", tu DOIS les utiliser EN PRIORITÉ dans ta réponse.
Ces corrections ont été validées par des administrateurs et remplacent toute autre information contradictoire.

**IMPORTANT** : Quand tu utilises une correction prioritaire dans ta réponse, tu DOIS l'indiquer clairement en ajoutant à la fin de ta réponse :

> ℹ️ **Note** : Cette réponse inclut une correction validée par un administrateur.

**IMPORTANT - TEMPLATES DISPONIBLES** :
Tu as accès à des templates/documents que tu peux proposer et montrer à l'utilisateur :
- Conventions d'étude (standard, pro-bono, cadre)
- Avenants (de délai, de rupture, par email, au RM, à la Convention)
- Bons de commande (standard, rectificatif)
- Procès-verbaux de recette finale

**Quand l'utilisateur demande un template, un modèle, un exemple, un avenant, une convention, etc. :**
1. Réponds positivement : "Oui, j'ai un template de [nom du document] à te proposer !"
2. Explique brièvement son contenu et son utilité
3. Le système détectera automatiquement la demande et fournira le fichier

**Ne dis JAMAIS** : "Je ne peux pas fournir/montrer de template" car tu EN AS !

📝 **FORMAT DE RÉPONSE - MARKDOWN** :
Structure TOUJOURS tes réponses en Markdown bien formaté :

- Utilise **## Titre principal** pour les sections importantes
- Utilise **### Sous-titres** pour les sous-sections
- Utilise des **listes à puces** (* ou -) pour énumérer des éléments
- Utilise des **listes numérotées** (1., 2., 3.) pour des étapes
- Utilise **\`code\`** pour les termes techniques ou noms de documents
- Utilise **gras** pour mettre en évidence des points importants
- Utilise des **> citations** pour les références légales
- Saute des lignes entre les paragraphes pour l'aération

Exemple de structure :
```markdown
## Titre de la réponse

Paragraphe introductif clair.

### Point important

* Premier élément
* Deuxième élément
* Troisième élément

**Important :** Information clé à retenir.
```

Réponds de façon factuelle, concise, structurée et proactive. Si le contexte contient l'information, utilise-la pour une réponse précise.

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


def generate_answer(query: str, conversation_history: List[Dict[str, Any]] = None, system_prompt: str = None) -> Tuple[str, List[Tuple[str, str]], Optional[str]]:
    if conversation_history is None:
        conversation_history = []

    history = format_conversation_history(conversation_history)
    
    admin_corrections = []
    try:
        admin_corrections = vector_store.similarity_search(
            query,
            k=3, 
            filter={"$and": [{"type": {"$eq": "admin_correction"}}, {"priority": {"$eq": "high"}}]}
        )
    except Exception as e:
        print(f"Erreur lors de la recherche des corrections: {e}")
        admin_corrections = []
    
    context_docs = retriever.get_relevant_documents(query)
    
    context_parts = []
    if admin_corrections:
        context_parts.append("=== CORRECTIONS PRIORITAIRES (À UTILISER EN PREMIER) ===")
        context_parts.extend([d.page_content for d in admin_corrections])
        context_parts.append("\n=== DOCUMENTATION STANDARD ===")
    
    context_parts.extend([d.page_content for d in context_docs])
    context = "\n".join(context_parts)

    full_prompt = custom_prompt.format(conversation_history=history, context=context, question=query)
    
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{full_prompt}"
    
    response = llm.invoke(full_prompt)
    answer = response.content if hasattr(response, 'content') else str(response)
    sources = [(d.metadata.get('source'), d.metadata.get('page')) for d in context_docs]


    # Détection du template demandé
    requested_template = detect_template_with_ai(llm, query, AVAILABLE_TEMPLATES)
    template_path = None
    
    if requested_template:
        template_path = get_template_path(requested_template)

    answer = re.sub(r"TEMPLATE_REQUEST:\s*.+?(?:\n|$)", "", answer, flags=re.IGNORECASE).strip()
    return answer, sources, template_path
