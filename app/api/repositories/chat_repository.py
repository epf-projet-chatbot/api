"""
Repository pour la gestion des discussions en MongoDB
"""

from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from api.models.chat_model import Chat
from motor.motor_asyncio import AsyncIOMotorDatabase

class ChatRepository:
    """Repository pour les opérations CRUD sur les discussions"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.collection = database.chats
    
    async def create_indexes(self):
        """Créer les index nécessaires"""
        await self.collection.create_index("created_at")
    
    async def create_chat(self, chat_data: dict) -> dict:
        """Créer une nouvelle discussion"""
        chat_data["created_at"] = datetime.utcnow()
        result = await self.collection.insert_one(chat_data)
        chat_data["_id"] = result.inserted_id
        return chat_data
    
    async def get_chat_by_id(self, chat_id: str) -> Optional[dict]:
        """Récupérer une discussion par son ID"""
        chat_doc = await self.collection.find_one({"_id": ObjectId(chat_id)})
        if chat_doc:
            return chat_doc
        return None
    
    async def get_chats_by_user_id(self, user_id: str) -> List[dict]:
        """Récupérer toutes les discussions d'un utilisateur"""
        chats = []
        async for chat in self.collection.find({"user_id": ObjectId(user_id)}):
            chats.append(chat)
        return chats
    
    async def update_chat(self, chat_id: str, update_data: dict) -> Optional[dict]:
        """Mettre à jour une discussion"""
        update_data["updated_at"] = datetime.utcnow()
        result = await self.collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$set": update_data}
        )
        if result.modified_count > 0:
            return await self.get_chat_by_id(chat_id)
        return None
    
    async def delete_chat(self, chat_id: str) -> bool:
        """Supprimer une discussion"""
        result = await self.collection.delete_one({"_id": ObjectId(chat_id)})
        return result.deleted_count > 0