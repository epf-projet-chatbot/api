import re
from typing import Optional

def detect_template_with_ai(llm, query: str, templates_dict) -> Optional[str]:
    query_lower = query.lower()
    
    # Mapping direct pour les cas courants (c'est plus rapide)
    keyword_mapping = {
        "avenant de délai": "Avenant à la Convention d'Etude - AGP_CRP_25.pdf",
        "avenant délai": "Avenant à la Convention d'Etude - AGP_CRP_25.pdf",
        "avenant de rupture": "Avenant-de-Rupture-à-la-Convention-dEtude.pdf",
        "avenant rupture": "Avenant-de-Rupture-à-la-Convention-dEtude.pdf",
        "convention d'étude": "Convention d'Etude - AGP_CRP_25.pdf",
        "convention étude": "Convention d'Etude - AGP_CRP_25.pdf",
        "convention cadre": "Convention Cadre - AGP_CRP_25.pdf",
        "pro bono": "Convention d'Etude Pro-Bono - AGP_Sept_24 - V0 2024.06.14.pdf",
        "pro-bono": "Convention d'Etude Pro-Bono - AGP_Sept_24 - V0 2024.06.14.pdf",
        "bon de commande": "Bon de Commande - AGP_CRP_25.pdf",
        "procès-verbal": "Procès-Verbal de Recette Finale - AGP_CRP_25.pdf",
        "pv de recette": "Procès-Verbal de Recette Finale - AGP_CRP_25.pdf",
    }

    for keyword, filename in keyword_mapping.items():
        if keyword in query_lower and filename in templates_dict:
            return filename

    template_list = "\n".join([f"- {fn}: {desc}" for fn, desc in templates_dict.items()])
    prompt = f"""Tu es un assistant qui identifie quel document juridique l'utilisateur demande.

Voici la liste des documents disponibles :
{template_list}

Question de l'utilisateur : "{query}"

**Instructions** :
- Identifie le document le plus pertinent
- Si l'utilisateur demande un "avenant" sans préciser, choisis "Avenant à la Convention d'Etude - AGP_CRP_25.pdf"
- Si tu hésites entre plusieurs documents, choisis le plus générique

Réponds UNIQUEMENT avec le nom EXACT du fichier (ex: "Avenant au Récapitulatif de Mission - AGP_CRP_25.pdf") ou "AUCUN" si aucun fichier ne correspond."""
    
    try:
        resp = llm.invoke(prompt)
        detected = resp.content.strip() if hasattr(resp, 'content') else str(resp).strip()
        # Nettoyer la réponse
        detected = detected.strip('"\'').strip()
        if detected != "AUCUN" and detected in templates_dict:
            return detected
    except Exception:
        return None
    return None
