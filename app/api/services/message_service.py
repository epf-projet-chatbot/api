"""
Service pour la gestion des messages (logique métier)
"""
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from bson import ObjectId

from api.repositories.message_repository import MessageRepository
from api.repositories.chat_repository import ChatRepository
from api.schemas.message_schemas import MessageCreate


class MessageService:
    """Service contenant la logique métier pour les messages"""
    
    def __init__(
        self, 
        message_repo: MessageRepository,
        chat_repo: ChatRepository
    ):
        self.message_repo = message_repo
        self.chat_repo = chat_repo
    
    async def create_message(
        self, 
        message_data: MessageCreate,
        user_id: Optional[str] = None
    ) -> str:
        """
        Créer un nouveau message
        Logique métier:
        - Vérifier que le chat existe
        - Convertir les attachments en format DB
        - Mettre à jour le titre du chat si c'est le premier message utilisateur
        """
        # cehck if data exist
        chat = await self.chat_repo.get_chat_by_id(message_data.discussion_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        # user secu
        if user_id and chat.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # convertir les attachments en dictionnaires
        attachments_list = None
        if message_data.attachments:
            attachments_list = []
            for attachment in message_data.attachments:
                if hasattr(attachment, 'dict'):
                    attachment_dict = attachment.dict()
                    if 'url' in attachment_dict and hasattr(attachment_dict['url'], '__str__'):
                        attachment_dict['url'] = str(attachment_dict['url'])
                    attachments_list.append(attachment_dict)
                else:
                    if 'url' in attachment and hasattr(attachment['url'], '__str__'):
                        attachment['url'] = str(attachment['url'])
                    attachments_list.append(attachment)


        message_id = await self.message_repo.create(
            discussion_id=message_data.discussion_id,
            content=message_data.content,
            role=message_data.role,
            attachments=attachments_list
        )
        
        # if it's the first message, we update chat title
        if message_data.role == "user":
            await self._update_chat_title_if_needed(
                message_data.discussion_id, 
                message_data.content
            )
        
        return message_id
    
    async def _update_chat_title_if_needed(self, discussion_id: str, content: str):
        """Met à jour le titre du chat avec le premier message"""
        user_message_count = await self.message_repo.count_user_messages_in_chat(discussion_id)
    
        if user_message_count == 1:
            new_title = self._generate_chat_title(content)
            await self.chat_repo.update_chat(discussion_id, {"topic": new_title})
    
    def _generate_chat_title(self, first_message: str, max_length: int = 50) -> str:
        """Génère un titre de chat basé sur le premier message"""
        title = first_message.strip()
        if len(title) > max_length:
            title = title[:max_length-3] + "..."
        if len(title) < 3:
            title = "Nouvelle discussion"
        return title
    
    async def get_message_by_id(self, message_id: str) -> Dict[str, Any]:
        """Récupérer un message par ID"""
        message = await self.message_repo.get_by_id(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message with id {message_id} not found"
            )
        return message
    
    async def get_chat_messages(self, discussion_id: str) -> List[Dict[str, Any]]:
        """Récupérer tous les messages d'un chat"""
        if not ObjectId.is_valid(discussion_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid discussion_id format"
            )
        
        messages = await self.message_repo.get_by_chat_id(discussion_id)
        return messages
    
    async def get_conversation_history(
        self, 
        discussion_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Récupérer l'historique simplifié d'une conversation
        Logique métier: valider la limite
        """
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 100"
            )
        
        if not ObjectId.is_valid(discussion_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid discussion_id format"
            )
        
        history = await self.message_repo.get_conversation_history(discussion_id, limit)
        return history
    
    async def delete_message(self, message_id: str) -> bool:
        """Supprimer un message"""
        success = await self.message_repo.delete(message_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message with id {message_id} not found"
            )
        return True
