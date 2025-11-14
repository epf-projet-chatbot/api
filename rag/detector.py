import re
from typing import Optional

def detect_template_with_ai(llm, query: str, templates_dict) -> Optional[str]:
    template_list = "\n".join([f"- {fn}: {desc}" for fn, desc in templates_dict.items()])
    prompt = f"""Tu es un assistant qui identifie quel document juridique l'utilisateur demande.\n\nVoici la liste des documents disponibles :\n{template_list}\n\nQuestion de l'utilisateur : \"{query}\"\n\nRéponds UNIQUEMENT avec le nom EXACT du fichier (ex: "Avenant au Récapitulatif de Mission - AGP_CRP_25.pdf") ou "AUCUN" si aucun fichier ne correspond."""
    try:
        resp = llm.invoke(prompt)
        detected = resp.content.strip() if hasattr(resp, 'content') else str(resp).strip()
        if detected != "AUCUN" and detected in templates_dict:
            return detected
    except Exception:
        return None
    return None
