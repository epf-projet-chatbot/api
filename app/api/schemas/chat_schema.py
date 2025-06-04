from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatCreate(BaseModel):
    """
    Schéma pour créer une nouvelle session de chat.
    """
    user_id: str
    topic: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = []

class ChatUpdate(BaseModel):
    """
    Schéma pour mettre à jour une session de chat.
    """
    topic: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None

class Chat(BaseModel):
    """
    Représente une session de chat.
    """
    id: str
    user_id: str
    messages: List[Dict[str, Any]]  # Liste des messages échangés dans la session de chat
    created_at: datetime  # Date de création de la session de chat
    updated_at: datetime  # Date de dernière mise à jour de la session de chat
    topic: str  # Sujet du chat, par exemple "droit du travail", "droit fiscal", etc.

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }
