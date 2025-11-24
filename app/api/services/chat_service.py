"""
Service pour la gestion des chats (logique métier)
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId

from api.repositories.chat_repository import ChatRepository
from api.repositories.message_repository import MessageRepository
from api.repositories.upload_repository import UploadRepository
from api.schemas.chat_schema import ChatCreate, ChatUpdate


class ChatService:
    """Service contenant la logique métier pour les chats"""
    
    def __init__(
        self, 
        chat_repo: ChatRepository,
        message_repo: MessageRepository,
        upload_repo: UploadRepository
    ):
        self.chat_repo = chat_repo
        self.message_repo = message_repo
        self.upload_repo = upload_repo
    
    async def create_chat(self, data: ChatCreate, user_id: str) -> Dict[str, Any]:
        """
        Créer un nouveau chat
        Logique métier: ajouter l'user_id, initialiser le titre par défaut
        """
        data.user_id = user_id
        
        if not data.topic or data.topic.strip() == "":
            data.topic = "Nouvelle discussion"
        
        chat_dict = data.model_dump()
        chat = await self.chat_repo.create_chat(chat_dict)
        
        if "_id" in chat:
            chat["id"] = chat["_id"]
            del chat["_id"]

        if "updated_at" not in chat or chat["updated_at"] is None:
            chat["updated_at"] = chat.get("created_at", datetime.utcnow())
        
        return chat
    
    async def get_user_chats(self, user_id: str) -> List[Dict[str, Any]]:
        """Récupérer tous les chats d'un utilisateur"""
        chats = await self.chat_repo.get_chats_by_user_id(user_id)

        for chat in chats:
            if "_id" in chat:
                chat["id"] = chat["_id"]
                del chat["_id"]

            if "updated_at" not in chat or chat["updated_at"] is None:
                chat["updated_at"] = chat.get("created_at", datetime.utcnow())

            if "messages" in chat:
                del chat["messages"]

            if "topic" not in chat or chat["topic"] is None:
                chat["topic"] = "Nouvelle discussion"
        
        return chats
    
    async def get_chat_by_id(
        self, 
        chat_id: str, 
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Récupérer un chat par ID
        Logique métier: vérifier que le chat appartient à l'utilisateur
        """
        if not ObjectId.is_valid(chat_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid chat ID format"
            )
        
        chat = await self.chat_repo.get_chat_by_id(chat_id)
        
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )

        if chat.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        if "_id" in chat:
            chat["id"] = chat["_id"]
            del chat["_id"]

        if "updated_at" not in chat or chat["updated_at"] is None:
            chat["updated_at"] = chat.get("created_at", datetime.utcnow())
        
        return chat
    
    async def update_chat_title(self, chat_id: str, title: str) -> bool:
        """Mettre à jour le titre d'un chat"""
        return await self.chat_repo.update_chat(chat_id, {"topic": title})
    
    async def delete_chat(self, chat_id: str, user_id: str) -> bool:
        """
        Supprimer un chat avec suppression en cascade
        Logique métier: 
        - Vérifier la propriété
        - Supprimer les fichiers associés
        - Supprimer les messages
        - Supprimer le chat
        """
        if not ObjectId.is_valid(chat_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid chat ID format"
            )

        chat = await self.chat_repo.get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        if chat.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        await self._delete_chat_files(chat_id)

        await self.message_repo.delete_by_chat_id(chat_id)

        success = await self.chat_repo.delete_chat(chat_id)
        return success
    
    async def _delete_chat_files(self, chat_id: str) -> int:
        """Supprimer tous les fichiers associés à un chat"""
        deleted_count = 0

        messages = await self.message_repo.find_messages_with_attachments(chat_id)
        
        for message in messages:
            if "attachments" in message and message["attachments"]:
                for attachment in message["attachments"]:
                    if "url" in attachment:
                        url = attachment["url"]

                        if "/upload/gridfs/" in url or "/files/gridfs/" in url:
                            file_id = url.split("/")[-1]
                            try:
                                await self.upload_repo.delete_file(file_id)
                                deleted_count += 1
                            except Exception:
                                continue
        
        return deleted_count
    
    def generate_chat_title(self, first_message: str, max_length: int = 50) -> str:
        """Génère un titre de chat basé sur le premier message"""
        title = first_message.strip()
        if len(title) > max_length:
            title = title[:max_length-3] + "..."
        if len(title) < 3:
            title = "Nouvelle discussion"
        return title
