import os
from typing import Optional

data_complete_path = os.path.join(os.path.dirname(__file__), "data", "data_complete")

AVAILABLE_TEMPLATES = {
    "Convention d'Etude - AGP_CRP_25.pdf": "Convention d'étude standard pour les missions",
    "Convention Cadre - AGP_CRP_25.pdf": "Convention cadre pour partenariats à long terme",
    "Convention d'Etude Pro-Bono - AGP_Sept_24 - V0 2024.06.14.pdf": "Convention d'étude pro-bono gratuite",
    "Avenant au Récapitulatif de Mission - AGP_CRP_25.pdf": "Avenant pour modifier un récapitulatif de mission (RM)",
    "Avenant-de-Rupture-au-Récapitulatif-de-Mission.pdf": "Avenant de rupture d'un récapitulatif de mission",
    "Avenant à la Convention d'Etude - AGP_CRP_25.pdf": "Avenant pour modifier une convention d'étude",
    "Avenant-de-Rupture-à-la-Convention-dEtude.pdf": "Avenant de rupture d'une convention d'étude",
    "Avenant par mail à la Convention d'Etude - AGP_CRP_25.pdf": "Avenant par email à une convention",
    "Avenant-a-la-Convention-Cadre-1.pdf": "Avenant pour modifier une convention cadre",
    "Bon de Commande - AGP_CRP_25.pdf": "Bon de commande standard",
    "Bon de Commande Rectificatif - AGP_CRP_25.pdf": "Bon de commande rectificatif pour corriger un BC existant",
    "Procès-Verbal de Recette Finale - AGP_CRP_25.pdf": "Procès-verbal de recette finale (PV de recette)",
}

def get_template_path(filename: str) -> Optional[str]:
    """Return absolute template file path when available."""

    path = os.path.join(data_complete_path, filename)
    return path if os.path.exists(path) else None
