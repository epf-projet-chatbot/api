from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime
from beanie import PydanticObjectId

class Attachment(BaseModel):
    filename: str = Field(..., description="Nom du fichier")
    url: HttpUrl = Field(..., description="URL de la pièce jointe")

class MessageSchema(BaseModel):
    id: Optional[str]=None
    discussion_id: PydanticObjectId = Field(..., description="ID de la discussion", examples=["60d5ec49f8d2e4b8b4e7b8c2"])
    content: str = Field(..., description="Contenu du message", examples=["Bonjour, comment ça va ?"])
    date_created: datetime = Field(..., description="Date de création du message", examples=["2023-10-01T12:00:00Z"])
    attachments: Optional[List[Attachment]] = Field(None, description="Liste des pièces jointes")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "a1",
                "discussion_id": "60d5ec49f8d2e4b8b4e7b8c2",
                "content": "Bonjour, comment ça va ?",
                "date_created": "2023-10-01T12:00:00Z",
                "attachments": [
                    {
                        "filename": "image.png",
                        "url": "https://example.com/image.png"
                    }
                ],
            }
        }

class MessageCreate(BaseModel):
    discussion_id: PydanticObjectId = Field(..., description="ID de la discussion")
    content: str = Field(..., description="Contenu du message")
    role: Optional[str] = Field("user", description="Rôle de l'expéditeur du message (par exemple, 'user', 'bot')")
    attachments: Optional[List[Attachment]] = Field(None, description="Liste des pièces jointes")

class MessageUpdate(BaseModel):
    content: Optional[str] = Field(None, description="Nouveau contenu du message")
    attachments: Optional[List[Attachment]] = Field(None, description="Liste des pièces jointes")

class MessageDelete(BaseModel):
    id: str = Field(..., description="ID du message à supprimer")

class MessageResponse(BaseModel):
    message: str = Field(..., description="Message de réponse")
    data: Optional[MessageSchema] = Field(None, description="Données du message")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Message récupéré avec succès",
                "data": {
                    "id": "60d5ec49f8d2e4b8b4e7b8c0",
                    "user_id": "60d5ec49f8d2e4b8b4e7b8c1",
                    "discussion_id": "60d5ec49f8d2e4b8b4e7b8c2",
                    "content": "Bonjour, comment ça va ?",
                    "date_created": "2023-10-01T12:00:00Z",
                    "date_updated": "2023-10-01T12:00:00Z",
                    "attachments": [
                        {
                            "filename": "image.png",
                            "url": "https://example.com/image.png"
                        }
                    ],
                }
            }
        }