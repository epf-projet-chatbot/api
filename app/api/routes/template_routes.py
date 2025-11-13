"""
Routes pour gérer les templates et documents
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter(
    prefix="/templates",
    tags=["Templates"]
)

# cehminn absolu vers les templates pour Docker : /app/rag/data/data_complete
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", "/app/rag/data/data_complete")

# fallback au cas où
if not os.path.exists(TEMPLATES_DIR):
    _current_file = os.path.abspath(__file__)
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_current_file))))
    TEMPLATES_DIR = os.path.join(_project_root, "rag", "data", "data_complete")

@router.get("/{filename}")
async def get_template_file(filename: str):
    """
    Télécharger un fichier template
    """
    try:
        # on met un security layer ici
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Nom de fichier invalide")
        
        file_path = os.path.join(TEMPLATES_DIR, filename)
    
        if not os.path.exists(file_path):
            # Message d'erreur détaillé pour le debug
            error_msg = f"Fichier template non trouvé: {filename}"
            error_msg += f" | Chemin recherché: {file_path}"
            error_msg += f" | Dossier existe: {os.path.exists(TEMPLATES_DIR)}"
            if os.path.exists(TEMPLATES_DIR):
                error_msg += f" | Fichiers disponibles: {os.listdir(TEMPLATES_DIR)}"
            raise HTTPException(status_code=404, detail=error_msg)
        
        # Vérifier que c'est bien un fichier dans le dossier templates
        if not os.path.abspath(file_path).startswith(os.path.abspath(TEMPLATES_DIR)):
            raise HTTPException(status_code=403, detail="Accès interdit")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération du template: {str(e)}")


@router.get("/")
async def list_available_templates():
    """
    Lister tous les templates disponibles
    """
    try:
        templates = []
        
        if os.path.exists(TEMPLATES_DIR):
            for filename in os.listdir(TEMPLATES_DIR):
                file_path = os.path.join(TEMPLATES_DIR, filename)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    templates.append({
                        "filename": filename,
                        "size": file_size,
                        "url": f"/templates/{filename}"
                    })
        
        return {
            "templates": templates,
            "count": len(templates),
            "templates_dir": TEMPLATES_DIR,
            "dir_exists": os.path.exists(TEMPLATES_DIR)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la liste des templates: {str(e)}")
