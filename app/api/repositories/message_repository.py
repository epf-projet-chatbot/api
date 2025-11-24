"""
Repository pour la gestion des messages en base de données
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import re
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase


class MessageRepository:
    """Repository pour les opérations CRUD sur les messages"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.messages
        self.collection_user = database.users
    
    async def create(
        self, 
        discussion_id: str, 
        content: str, 
        role: str = "user", 
        attachments: Optional[List[dict]] = None
    ) -> str:
        """
        Créer un nouveau message en DB
        Returns: ID du message créé
        """
        message_data = {
            "discussion_id": ObjectId(discussion_id),
            "content": content,
            "role": role,
            "date_created": datetime.now(),
            "attachments": attachments or []
        }
        
        result = await self.collection.insert_one(message_data)
        return str(result.inserted_id)
    
    async def get_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer un message par son ID"""
        try:
            message_doc = await self.collection.find_one({"_id": ObjectId(message_id)})
            if message_doc:
                message_doc["_id"] = str(message_doc["_id"])
                if "discussion_id" in message_doc:
                    message_doc["discussion_id"] = str(message_doc["discussion_id"])
                return message_doc
            return None
        except InvalidId:
            return None
    
    async def get_by_chat_id(self, discussion_id: str) -> List[Dict[str, Any]]:
        """Récupérer tous les messages d'une discussion"""
        try:
            discussion_obj_id = ObjectId(discussion_id)
            cursor = self.collection.find({"discussion_id": discussion_obj_id})
            messages = []
            async for msg in cursor:
                msg["_id"] = str(msg["_id"])
                if "discussion_id" in msg:
                    msg["discussion_id"] = str(msg["discussion_id"])
                messages.append(msg)
            return messages
        except InvalidId:
            return []
    
    async def get_conversation_history(
        self, 
        discussion_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Récupérer l'historique simplifié des messages
        Returns: Liste de messages avec seulement role, content, date_created
        """
        try:
            discussion_obj_id = ObjectId(discussion_id)
            cursor = self.collection.find(
                {"discussion_id": discussion_obj_id}
            ).sort("date_created", -1).limit(limit)
            
            messages = []
            async for msg in cursor:
                simplified_msg = {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "date_created": msg.get("date_created")
                }
                messages.append(simplified_msg)
            
            messages.reverse()
            return messages
        except InvalidId:
            return []
    
    async def count_user_messages_in_chat(self, discussion_id: str) -> int:
        """Compter le nombre de messages utilisateur dans un chat"""
        try:
            return await self.collection.count_documents({
                "discussion_id": ObjectId(discussion_id),
                "role": "user"
            })
        except InvalidId:
            return 0
    
    async def delete(self, message_id: str) -> bool:
        """Supprimer un message"""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(message_id)})
            return result.deleted_count > 0
        except InvalidId:
            return False
    
    async def delete_by_chat_id(self, discussion_id: str) -> int:
        """
        Supprimer tous les messages d'un chat
        Returns: Nombre de messages supprimés
        """
        try:
            result = await self.collection.delete_many({
                "discussion_id": ObjectId(discussion_id)
            })
            return result.deleted_count
        except InvalidId:
            return 0
    
    async def find_messages_with_attachments(self, discussion_id: str) -> List[Dict[str, Any]]:
        """Trouver tous les messages avec attachments dans un chat"""
        try:
            cursor = self.collection.find({
                "discussion_id": ObjectId(discussion_id),
                "attachments": {"$exists": True, "$ne": []}
            })
            
            messages = []
            async for msg in cursor:
                msg["_id"] = str(msg["_id"])
                if "discussion_id" in msg:
                    msg["discussion_id"] = str(msg["discussion_id"])
                messages.append(msg)
            return messages
        except InvalidId:
            return []
        
    async def system_correction_chatbot(self, user_id: str, message: str, discussion_id: str):
        """Si l'utilisateur est un admin et fait /correction, ajoute la correction dans ChromaDB"""
        try:
            match = re.match(r'^/correction\s+(.+)$', message, re.IGNORECASE)
            if not match:
                return None 
            correction = match.group(1)

            user = await self.collection_user.find_one(
                {"_id": ObjectId(user_id)},
                {"admin": 1, "_id": 0}
            )

            user_admin = user.get("admin", "user") if user else "user"
            
            if not user_admin:
                return {"error": "Accès refusé : vous devez être admin"}
            if (user_admin !="admin" and user_admin != "superadmin"):
                return {"error": "Accès refusé : vous devez être admin"}
            
            recent_messages = await self.get_conversation_history(discussion_id, limit=5)
            context_question = ""
            if recent_messages:
                for msg in reversed(recent_messages):
                    if msg.get("role") == "user" and not msg.get("content", "").startswith("/"):
                        context_question = msg.get("content", "")
                        break
            
            from rag.embedding import add_correction_to_chroma
            correction_id = await add_correction_to_chroma(
                correction_text=correction,
                context_question=context_question,
                admin_id=user_id,
                discussion_id=discussion_id
            )
            
            return {
                "success": True,
                "correction": correction,
                "correction_id": correction_id,
                "message": "Correction ajoutée avec succès et sera prioritaire dans les futures réponses"
            }

        except Exception as e:
            return {"error": str(e)}
    
    async def count_messages(self) -> int:
        """Compter le nombre total de messages"""
        return await self.collection.count_documents({})

