from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime


class UploadResponse(BaseModel):
    """Schéma de réponse pour un upload de fichier"""
    
    id: str = Field(..., description="ID unique du fichier uploadé")
    filename: str = Field(..., description="Nom original du fichier")
    url: str = Field(..., description="URL d'accès au fichier")
    file_path: str = Field(..., description="Chemin du fichier sur le serveur")
    file_size: int = Field(..., description="Taille du fichier en bytes")
    content_type: str = Field(..., description="Type MIME du fichier")
    uploaded_at: datetime = Field(..., description="Date d'upload")
    user_id: Optional[str] = Field(None, description="ID de l'utilisateur qui a uploadé")
    storage_type: Optional[str] = Field("filesystem", description="Type de stockage: filesystem ou gridfs")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "filename": "document.pdf",
                "url": "http://localhost:8000/files/gridfs/507f1f77bcf86cd799439011",
                "file_path": "gridfs://507f1f77bcf86cd799439011",
                "file_size": 1024000,
                "content_type": "application/pdf",
                "uploaded_at": "2025-06-11T14:30:00Z",
                "user_id": "507f1f77bcf86cd799439012",
                "storage_type": "gridfs"
            }
        }


class FileMetadata(BaseModel):
    """Métadonnées d'un fichier pour la base de données"""
    
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    content_type: str
    uploaded_at: datetime
    user_id: Optional[str] = None
