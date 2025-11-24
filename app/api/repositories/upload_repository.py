"""
Repository pour la gestion des fichiers uploadés (GridFS et métadonnées)
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket


class UploadRepository:
    """Repository pour les opérations sur les fichiers GridFS"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.gridfs_bucket = AsyncIOMotorGridFSBucket(database, bucket_name="files")
        self.files_collection = database.get_collection("files.files")
    
    async def upload_to_gridfs(
        self, 
        filename: str, 
        content: bytes, 
        metadata: dict
    ) -> str:
        """
        Uploader un fichier dans GridFS
        Returns: ID du fichier
        """
        file_id = await self.gridfs_bucket.upload_from_stream(
            filename=filename,
            source=content,
            metadata=metadata
        )
        return str(file_id)
    
    async def get_file_content(self, file_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Récupérer le contenu d'un fichier GridFS
        Returns: (content, metadata)
        """
        grid_out = await self.gridfs_bucket.open_download_stream(ObjectId(file_id))
        content = await grid_out.read()
        
        metadata = {
            "filename": grid_out.filename,
            "content_type": grid_out.metadata.get("content_type", "application/octet-stream"),
            "file_size": grid_out.length,
            "uploaded_at": grid_out.metadata.get("uploaded_at")
        }
        
        return content, metadata
    
    async def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer uniquement les métadonnées d'un fichier"""
        try:
            grid_file = await self.files_collection.find_one({"_id": ObjectId(file_id)})
            if grid_file:
                return {
                    "id": str(grid_file["_id"]),
                    "filename": grid_file.get("filename"),
                    "file_size": grid_file.get("length", 0),
                    "content_type": grid_file.get("metadata", {}).get("content_type", "application/octet-stream"),
                    "uploaded_at": grid_file.get("metadata", {}).get("uploaded_at", grid_file.get("uploadDate")),
                    "user_id": grid_file.get("metadata", {}).get("user_id")
                }
            return None
        except Exception:
            return None
    
    async def get_files_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Récupérer tous les fichiers d'un utilisateur"""
        cursor = self.files_collection.find({
            "$or": [
                {"metadata.user_id": user_id},
                {"metadata.user_id": str(user_id)}
            ]
        })
        
        files = []
        async for grid_file in cursor:
            file_data = {
                "id": str(grid_file["_id"]),
                "filename": grid_file.get("filename"),
                "file_size": grid_file.get("length", 0),
                "content_type": grid_file.get("metadata", {}).get("content_type", "application/octet-stream"),
                "uploaded_at": grid_file.get("metadata", {}).get("uploaded_at", grid_file.get("uploadDate")),
                "user_id": user_id
            }
            files.append(file_data)
        
        return files
    
    async def delete_file(self, file_id: str) -> bool:
        """Supprimer un fichier GridFS"""
        try:
            await self.gridfs_bucket.delete(ObjectId(file_id))
            return True
        except Exception:
            return False
    
    async def file_exists(self, file_id: str) -> bool:
        """Vérifier si un fichier existe"""
        try:
            grid_file = await self.files_collection.find_one({"_id": ObjectId(file_id)})
            return grid_file is not None
        except Exception:
            return False
    
    async def verify_user_ownership(self, file_id: str, user_id: str) -> bool:
        """Vérifier qu'un fichier appartient à un utilisateur"""
        try:
            grid_file = await self.files_collection.find_one({"_id": ObjectId(file_id)})
            if not grid_file:
                return False
            
            metadata = grid_file.get("metadata", {})
            file_user_id = metadata.get("user_id") if metadata else None
            
            return str(file_user_id) == str(user_id)
        except Exception:
            return False
