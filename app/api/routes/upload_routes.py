"""
Routes pour l'upload de fichiers
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Response
from typing import List
from bson import ObjectId

from api.services.upload_service import UploadService
from api.schemas.upload_schemas import UploadResponse
from core.dependencies import get_upload_service, get_current_user


router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/gridfs", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file_to_gridfs(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    upload_service: UploadService = Depends(get_upload_service)
):
    """Upload un fichier directement dans MongoDB GridFS (recommandé pour les PDFs)"""
    result = await upload_service.upload_file(file=file, user_id=current_user["_id"])
    return UploadResponse(**result)


@router.get("/gridfs/{file_id}")
async def download_gridfs_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    upload_service: UploadService = Depends(get_upload_service)
):
    """Télécharger un fichier depuis GridFS"""
    content, metadata = await upload_service.get_file_content(file_id)
    return Response(
        content=content,
        media_type=metadata["content_type"],
        headers={
            "Content-Disposition": f"inline; filename={metadata['filename']}",
            "Content-Length": str(metadata["file_size"])
        }
    )


@router.delete("/gridfs/{file_id}")
async def delete_gridfs_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    upload_service: UploadService = Depends(get_upload_service)
):
    """Supprimer un fichier GridFS de l'utilisateur connecté"""
    await upload_service.delete_file(file_id=file_id, user_id=current_user["_id"])
    return {"message": "Fichier GridFS supprimé avec succès"}


@router.get("/gridfs/list/active-files", response_model=List[UploadResponse])
async def get_my_active_gridfs_files(
    current_user: dict = Depends(get_current_user),
    upload_service: UploadService = Depends(get_upload_service)
):
    """
    Récupérer seulement les fichiers GridFS de l'utilisateur connecté qui sont liés à des messages existants
    (ne retourne pas les fichiers orphelins après suppression de chats)
    """
    files = await upload_service.get_active_user_files(current_user["_id"])
    return [UploadResponse(**file_data) for file_data in files]


@router.delete("/gridfs/cleanup/orphaned")
async def cleanup_orphaned_gridfs_files(
    current_user: dict = Depends(get_current_user),
    upload_service: UploadService = Depends(get_upload_service)
):
    """
    Nettoyer les fichiers GridFS orphelins (non liés à des messages existants) de l'utilisateur connecté
    """
    deleted_count = await upload_service.cleanup_orphaned_files(current_user["_id"])
    return {
        "message": f"Nettoyage terminé: {deleted_count} fichiers orphelins supprimés",
        "deleted_count": deleted_count
    }
