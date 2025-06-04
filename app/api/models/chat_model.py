from typing import Optional, Any, List, Dict
from pydantic import BaseModel
from datetime import datetime


class Chat(BaseModel):
    """Modèle pour une session de chat"""
    
    id: Optional[str] = None
    user_id: str  # ID de l'utilisateur
    messages: List[Dict[str, Any]] = []  # Liste des messages dans la discussion
    created_at: Optional[datetime] = None  # Date de création de la discussion
    updated_at: Optional[datetime] = None  # Date de la dernière mise à jour
    topic: Optional[str] = None  # Sujet de la discussion

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "user_id": "60c72b2f9b1e8d001c8e4f3a",
                "messages": [
                    {"role": "user", "content": "Bonjour, comment ça va ?"},
                    {"role": "bot", "content": "Ça va bien, merci ! Et vous ?"}
                ],
                "topic": "Conversation générale"
            }
        }