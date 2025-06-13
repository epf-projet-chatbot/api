"""
Contrôleur pour la gestion des uploads de fichiers
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import UploadFile, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from bson import ObjectId

from api.schemas.upload_schemas import UploadResponse, FileMetadata
from core.config import settings


class UploadController:
    """Contrôleur pour les opérations d'upload de fichiers"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        
        # Configuration GridFS pour stocker les fichiers en BDD
        self.gridfs_bucket = AsyncIOMotorGridFSBucket(database, bucket_name="files")
        
        print(f"🏗️ CONSTRUCTOR: UploadController init with database: {self.database}")
        print(f"🏗️ CONSTRUCTOR: GridFS bucket: {self.gridfs_bucket}")

    async def upload_file_to_db(self, file: UploadFile, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload un fichier directement dans MongoDB GridFS
        """
        try:
            # Validation du fichier
            if not file.filename:
                raise HTTPException(status_code=400, detail="Nom de fichier manquant")
            
            # Lire le contenu du fichier
            content = await file.read()
            file_size = len(content)
            
            # Validation de la taille (par exemple, max 16MB pour GridFS)
            max_size = 16 * 1024 * 1024  # 16MB (limite GridFS)
            if file_size > max_size:
                raise HTTPException(
                    status_code=413, 
                    detail=f"Fichier trop volumineux pour GridFS. Taille max: {max_size // (1024*1024)}MB"
                )
            
            # Métadonnées du fichier
            metadata = {
                "original_filename": file.filename,
                "content_type": file.content_type or "application/octet-stream",
                "uploaded_at": datetime.utcnow(),
                "user_id": user_id,
                "file_size": file_size
            }
            
            # Stocker le fichier dans GridFS
            file_id = await self.gridfs_bucket.upload_from_stream(
                filename=file.filename,
                source=content,
                metadata=metadata
            )
            
            # Créer l'URL d'accès pour GridFS
            file_url = f"{settings.base_url}/upload/gridfs/{str(file_id)}"
            
            print(f"📁 File uploaded to GridFS: {file.filename} (ID: {file_id}, {file_size} bytes)")
            
            return {
                "id": str(file_id),
                "filename": file.filename,
                "url": file_url,
                "file_path": f"gridfs://{str(file_id)}",  # Chemin virtuel
                "file_size": file_size,
                "content_type": metadata["content_type"],
                "uploaded_at": metadata["uploaded_at"],
                "user_id": user_id,
                "storage_type": "gridfs"
            }
            
        except Exception as e:
            print(f"❌ GridFS upload error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Erreur lors de l'upload GridFS: {str(e)}")

    async def get_gridfs_files(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Récupérer tous les fichiers GridFS d'un utilisateur
        """
        try:
            files = []
            
            print(f"🔍 Searching GridFS files for user_id: {user_id}")
            
            # Rechercher les fichiers par user_id dans les métadonnées en utilisant files.files
            files_collection = self.database.get_collection("files.files")
            cursor = files_collection.find({
                "$or": [
                    {"metadata.user_id": user_id},
                    {"metadata.user_id": str(user_id)}
                ]
            })
            
            async for grid_file in cursor:
                print(f"🔍 Found GridFS file: {grid_file.get('filename')} (user_id: {grid_file.get('metadata', {}).get('user_id')})")
                
                file_data = {
                    "id": str(grid_file["_id"]),
                    "filename": grid_file.get("filename"),
                    "url": f"{settings.base_url}/upload/gridfs/{str(grid_file['_id'])}",
                    "file_path": f"gridfs://{str(grid_file['_id'])}",
                    "file_size": grid_file.get("length", 0),
                    "content_type": grid_file.get("metadata", {}).get("content_type", "application/octet-stream"),
                    "uploaded_at": grid_file.get("metadata", {}).get("uploaded_at", grid_file.get("uploadDate")),
                    "user_id": user_id,
                    "storage_type": "gridfs"
                }
                files.append(file_data)
            
            print(f"🔍 Found {len(files)} GridFS files for user {user_id}")
            return files
            
        except Exception as e:
            print(f"❌ Error getting GridFS files: {str(e)}")
            return []

    async def get_active_gridfs_files(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Récupérer seulement les fichiers GridFS d'un utilisateur qui sont liés à des messages existants
        (évite de retourner les fichiers orphelins après suppression de chats)
        """
        try:
            active_files = []
            
            print(f"🔍 Searching active GridFS files for user_id: {user_id}")
            
            # 1. Récupérer tous les fichiers GridFS de l'utilisateur
            all_files = await self.get_gridfs_files(user_id)
            print(f"🔍 Found {len(all_files)} total GridFS files for user")
            
            # 2. Pour chaque fichier, vérifier s'il est référencé dans un message existant
            for file_data in all_files:
                file_id = file_data["id"]
                file_url = file_data["url"]
                
                # Chercher dans les messages si ce fichier est référencé
                message_with_file = await self.database.messages.find_one({
                    "attachments": {
                        "$elemMatch": {
                            "url": {"$regex": f".*{file_id}.*"}
                        }
                    }
                })
                
                if message_with_file:
                    print(f"✅ File {file_data['filename']} is active (linked to message {message_with_file.get('_id')})")
                    active_files.append(file_data)
                else:
                    print(f"🗑️ File {file_data['filename']} is orphaned (no message references it)")
            
            print(f"🔍 Found {len(active_files)} active GridFS files for user {user_id}")
            return active_files
            
        except Exception as e:
            print(f"❌ Error getting active GridFS files: {str(e)}")
            return []

    async def cleanup_orphaned_gridfs_files(self, user_id: str) -> int:
        """
        Supprimer tous les fichiers GridFS orphelins (non liés à des messages existants) de l'utilisateur
        """
        try:
            deleted_count = 0
            
            print(f"🧹 Starting cleanup of orphaned GridFS files for user_id: {user_id}")
            
            # 1. Récupérer tous les fichiers GridFS de l'utilisateur
            all_files = await self.get_gridfs_files(user_id)
            print(f"🔍 Found {len(all_files)} total GridFS files for user")
            
            # 2. Pour chaque fichier, vérifier s'il est orphelin
            for file_data in all_files:
                file_id = file_data["id"]
                
                # Chercher dans les messages si ce fichier est référencé
                message_with_file = await self.database.messages.find_one({
                    "attachments": {
                        "$elemMatch": {
                            "url": {"$regex": f".*{file_id}.*"}
                        }
                    }
                })
                
                if not message_with_file:
                    # Fichier orphelin - le supprimer
                    try:
                        print(f"🗑️ Deleting orphaned file: {file_data['filename']} ({file_id})")
                        await self.gridfs_bucket.delete(ObjectId(file_id))
                        deleted_count += 1
                        print(f"✅ Deleted orphaned file: {file_id}")
                    except Exception as e:
                        print(f"❌ Error deleting orphaned file {file_id}: {str(e)}")
                        continue
                else:
                    print(f"✅ File {file_data['filename']} is active (keeping it)")
            
            print(f"🧹 Cleanup completed: {deleted_count} orphaned files deleted")
            return deleted_count
            
        except Exception as e:
            print(f"❌ Error during orphaned files cleanup: {str(e)}")
            return 0

    async def get_gridfs_file_content(self, file_id: str) -> tuple[bytes, Dict[str, Any]]:
        """
        Récupérer le contenu d'un fichier GridFS
        """
        try:
            # Télécharger le fichier depuis GridFS
            grid_out = await self.gridfs_bucket.open_download_stream(ObjectId(file_id))
            content = await grid_out.read()
            
            # Récupérer les métadonnées
            metadata = {
                "filename": grid_out.filename,
                "content_type": grid_out.metadata.get("content_type", "application/octet-stream"),
                "file_size": grid_out.length,
                "uploaded_at": grid_out.metadata.get("uploaded_at")
            }
            
            return content, metadata
            
        except Exception as e:
            print(f"❌ Error getting GridFS file content: {str(e)}")
            raise HTTPException(status_code=404, detail="Fichier non trouvé dans GridFS")

    async def delete_gridfs_file(self, file_id: str, user_id: Optional[str] = None) -> bool:
        """
        Supprimer un fichier GridFS
        """
        try:
            print(f"🔍 Attempting to delete GridFS file: {file_id} for user: {user_id}")
            
            # Vérifier que le fichier existe en utilisant la collection files.files
            files_collection = self.database.get_collection("files.files")
            grid_file = await files_collection.find_one({"_id": ObjectId(file_id)})
            
            if not grid_file:
                print(f"❌ GridFS file not found: {file_id}")
                return False
            
            print(f"🔍 Found GridFS file: {grid_file.get('filename')}")
            print(f"🔍 File metadata: {grid_file.get('metadata', {})}")
            
            # Vérifier que le fichier appartient à l'utilisateur
            if user_id:
                metadata = grid_file.get("metadata", {})
                file_user_id = metadata.get("user_id") if metadata else None
                
                print(f"🔍 File user_id: {file_user_id} (type: {type(file_user_id).__name__})")
                print(f"🔍 Expected user_id: {user_id} (type: {type(user_id).__name__})")
                
                # Comparaison sécurisée en convertissant les deux en string
                if str(file_user_id) != str(user_id):
                    print(f"❌ Access denied: file belongs to {file_user_id}, not {user_id}")
                    return False
                else:
                    print(f"✅ Access granted: user IDs match")
            
            # Supprimer le fichier de GridFS
            await self.gridfs_bucket.delete(ObjectId(file_id))
            
            print(f"🗑️ GridFS file deleted successfully: {file_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting GridFS file: {str(e)}")
            return False


