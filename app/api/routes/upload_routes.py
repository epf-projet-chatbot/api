"""
Routes pour l'upload de fichiers
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from typing import List
from bson import ObjectId
from api.controllers.upload_controller import UploadController
from api.schemas.upload_schemas import UploadResponse
from core.database import get_database
from core.security import get_current_active_user
from bson import ObjectId


router = APIRouter(prefix="/upload", tags=["Upload"])


def get_upload_controller(db=Depends(get_database)) -> UploadController:
    """Dépendance pour obtenir le contrôleur d'upload"""
    controller = UploadController(db)
    return controller


@router.post("/gridfs", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file_to_gridfs(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
    upload_controller: UploadController = Depends(get_upload_controller)
):
    """
    Upload un fichier directement dans MongoDB GridFS (recommandé pour les PDFs)
    """
    try:
        # Upload du fichier avec l'ID de l'utilisateur connecté
        result = await upload_controller.upload_file_to_db(
            file=file,
            user_id=current_user["_id"]
        )
        
        return UploadResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'upload GridFS: {str(e)}"
        )


@router.get("/gridfs/{file_id}")
async def download_gridfs_file(
    file_id: str,
    current_user: dict = Depends(get_current_active_user),
    upload_controller: UploadController = Depends(get_upload_controller)
):
    """
    Télécharger un fichier depuis GridFS
    """
    try:
        from fastapi import Response
        content, metadata = await upload_controller.get_gridfs_file_content(file_id)
        return Response(
            content=content,
            media_type=metadata["content_type"],
            headers={
                "Content-Disposition": f"inline; filename={metadata['filename']}",
                "Content-Length": str(metadata["file_size"])
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du téléchargement: {str(e)}"
        )


@router.delete("/gridfs/{file_id}")
async def delete_gridfs_file(
    file_id: str,
    current_user: dict = Depends(get_current_active_user),
    upload_controller: UploadController = Depends(get_upload_controller)
):
    """
    Supprimer un fichier GridFS de l'utilisateur connecté
    """
    try:
        success = await upload_controller.delete_gridfs_file(
            file_id=file_id,
            user_id=current_user["_id"]
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fichier GridFS non trouvé ou accès non autorisé"
            )
        
        return {"message": "Fichier GridFS supprimé avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression GridFS: {str(e)}"
        )


@router.get("/gridfs/{file_id}/debug")
async def debug_gridfs_file(
    file_id: str,
    current_user: dict = Depends(get_current_active_user),
    upload_controller: UploadController = Depends(get_upload_controller)
):
    """
    Debug : Afficher les métadonnées d'un fichier GridFS pour diagnostiquer les problèmes
    """
    try:
        from bson import ObjectId
        
        files_collection = upload_controller.database.get_collection("files.files")
        grid_file = await files_collection.find_one({"_id": ObjectId(file_id)})
        
        if not grid_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fichier GridFS non trouvé"
            )
        debug_info = {
            "file_id": str(grid_file["_id"]),
            "filename": grid_file.get("filename"),
            "uploadDate": grid_file.get("uploadDate"),
            "length": grid_file.get("length"),
            "metadata": grid_file.get("metadata", {}),
            "current_user_id": current_user["_id"],
            "current_user_id_type": type(current_user["_id"]).__name__
        }
        metadata = grid_file.get("metadata", {})
        if metadata:
            file_user_id = metadata.get("user_id")
            debug_info["file_user_id"] = file_user_id
            debug_info["file_user_id_type"] = type(file_user_id).__name__ if file_user_id else "None"
            debug_info["user_id_match_strict"] = file_user_id == current_user["_id"]
            debug_info["user_id_match_string"] = str(file_user_id) == str(current_user["_id"])
        
        return {"debug_info": debug_info}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du debug: {str(e)}"
        )





@router.get("/gridfs/list/active-files", response_model=List[UploadResponse])
async def get_my_active_gridfs_files(
    current_user: dict = Depends(get_current_active_user),
    upload_controller: UploadController = Depends(get_upload_controller)
):
    """
    Récupérer seulement les fichiers GridFS de l'utilisateur connecté qui sont liés à des messages existants
    (ne retourne pas les fichiers orphelins après suppression de chats)
    """
    try:
        files = await upload_controller.get_active_gridfs_files(current_user["_id"])
        return [UploadResponse(**file_data) for file_data in files]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des fichiers GridFS actifs: {str(e)}"
        )


@router.delete("/gridfs/cleanup/orphaned")
async def cleanup_orphaned_gridfs_files(
    current_user: dict = Depends(get_current_active_user),
    upload_controller: UploadController = Depends(get_upload_controller)
):
    """
    Nettoyer les fichiers GridFS orphelins (non liés à des messages existants) de l'utilisateur connecté
    """
    try:
        deleted_count = await upload_controller.cleanup_orphaned_gridfs_files(current_user["_id"])
        return {
            "message": f"Nettoyage terminé: {deleted_count} fichiers orphelins supprimés",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du nettoyage des fichiers orphelins: {str(e)}"
        )
