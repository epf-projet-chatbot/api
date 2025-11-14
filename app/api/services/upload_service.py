"""
Service pour la gestion des uploads de fichiers (logique métier)
"""
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status, UploadFile

from api.repositories.upload_repository import UploadRepository
from api.repositories.message_repository import MessageRepository
from core.config import settings
from datetime import datetime


class UploadService:
    """Service contenant la logique métier pour les uploads"""
    
    def __init__(
        self, 
        upload_repo: UploadRepository,
        message_repo: MessageRepository
    ):
        self.upload_repo = upload_repo
        self.message_repo = message_repo
    
    async def upload_file(
        self, 
        file: UploadFile, 
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploader un fichier dans GridFS
        Logique métier:
        - Validation du fichier
        - Vérification de la taille
        - Génération de l'URL
        """
        # file name valiadtion
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is missing"
            )
        
        content = await file.read()
        file_size = len(content)
        
        # file size validation
        max_size = 16 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large for GridFS. Max size: {max_size // (1024*1024)}MB"
            )
        
        # prepare metadata
        metadata = {
            "original_filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "uploaded_at": datetime.utcnow(),
            "user_id": user_id,
            "file_size": file_size
        }
        
        # upload to gridfs via repository
        file_id = await self.upload_repo.upload_to_gridfs(
            filename=file.filename,
            content=content,
            metadata=metadata
        )
        
        # url generation
        file_url = f"{settings.base_url}/upload/gridfs/{file_id}"
        
        return {
            "id": file_id,
            "filename": file.filename,
            "url": file_url,
            "file_path": f"gridfs://{file_id}",
            "file_size": file_size,
            "content_type": metadata["content_type"],
            "uploaded_at": metadata["uploaded_at"],
            "user_id": user_id,
            "storage_type": "gridfs"
        }
    
    async def get_file_content(self, file_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Récupérer le contenu d'un fichier
        """
        try:
            content, metadata = await self.upload_repo.get_file_content(file_id)
            return content, metadata
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in GridFS"
            )
    
    async def get_user_files(self, user_id: str) -> List[Dict[str, Any]]:
        """Récupérer tous les fichiers d'un utilisateur"""
        files = await self.upload_repo.get_files_by_user(user_id)
        
        for file_data in files:
            file_id = file_data["id"]
            file_data["url"] = f"{settings.base_url}/upload/gridfs/{file_id}"
            file_data["file_path"] = f"gridfs://{file_id}"
            file_data["storage_type"] = "gridfs"
        
        return files
    
    async def get_active_user_files(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Récupérer seulement les fichiers actifs (liés à des messages existants)
        Logique métier: filtrer les fichiers orphelins
        """
        all_files = await self.get_user_files(user_id)
        active_files = []
        
        for file_data in all_files:
            file_id = file_data["id"]
            
            messages = await self.message_repo.find_messages_with_attachments("")
            is_active = False
            
            for message in messages:
                if "attachments" in message and message["attachments"]:
                    for attachment in message["attachments"]:
                        if "url" in attachment and file_id in attachment["url"]:
                            is_active = True
                            break
                if is_active:
                    break
            
            if is_active:
                active_files.append(file_data)
        
        return active_files
    
    async def delete_file(
        self, 
        file_id: str, 
        user_id: Optional[str] = None
    ) -> bool:
        """
        Supprimer un fichier
        Logique métier: vérifier la propriété si user_id fourni
        """
        if not await self.upload_repo.file_exists(file_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        if user_id:
            if not await self.upload_repo.verify_user_ownership(file_id, user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        
        success = await self.upload_repo.delete_file(file_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete file"
            )
        
        return True
    
    async def cleanup_orphaned_files(self, user_id: str) -> int:
        """
        Supprimer tous les fichiers orphelins d'un utilisateur
        Logique métier: trouver et supprimer les fichiers non référencés
        """
        deleted_count = 0
        all_files = await self.upload_repo.get_files_by_user(user_id)
        
        for file_data in all_files:
            file_id = file_data["id"]
            
            messages = await self.message_repo.find_messages_with_attachments("")
            is_orphaned = True
            
            for message in messages:
                if "attachments" in message and message["attachments"]:
                    for attachment in message["attachments"]:
                        if "url" in attachment and file_id in attachment["url"]:
                            is_orphaned = False
                            break
                if not is_orphaned:
                    break
            
            if is_orphaned:
                try:
                    await self.upload_repo.delete_file(file_id)
                    deleted_count += 1
                except Exception:
                    continue
        
        return deleted_count
