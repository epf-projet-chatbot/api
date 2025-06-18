from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatCreate(BaseModel):
    """
    Schéma pour créer une nouvelle session de chat.
    """
    user_id: str
    topic: str = "Nouvelle discussion"  # Sujet par défaut pour une nouvelle session de chat

class ChatUpdate(BaseModel):
    """
    Schéma pour mettre à jour une session de chat.
    """
    topic: Optional[str] = None

class Chat(BaseModel):
    """
    Représente une session de chat.
    """
    id: str
    user_id: str
    created_at: datetime  # Date de création de la session de chat
    updated_at: datetime  # Date de dernière mise à jour de la session de chat
    topic: Optional[str] = None  # Sujet du chat, par exemple "droit du travail", "droit fiscal", etc.

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }
