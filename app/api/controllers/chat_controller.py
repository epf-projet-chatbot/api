from bson import ObjectId
from api.schemas.chat_schema import ChatCreate, ChatUpdate
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase


class ChatController:
    """Contrôleur pour la gestion des chats"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.chats

    async def create_chat(self, data: ChatCreate) -> Dict[str, Any]:
        from datetime import datetime
        
        chat_dict = data.model_dump()
        chat_dict["created_at"] = datetime.utcnow()
        chat_dict["updated_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(chat_dict)
        
        inserted_doc = await self.collection.find_one({"_id": result.inserted_id})
        
        if inserted_doc:
            inserted_doc["id"] = str(inserted_doc["_id"])
            del inserted_doc["_id"]
            return inserted_doc
        else:
            return chat_dict

    async def get_all_chats(self,user:str) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"user_id": user})
        chats = []
        async for chat_doc in cursor:
            chat_doc["id"] = str(chat_doc["_id"])
            del chat_doc["_id"]
            chats.append(chat_doc)
        return chats

    async def get_chat_by_id(self, chat_id: str) -> Optional[Dict[str, Any]]:
        from bson import ObjectId
        chat_doc = await self.collection.find_one({"_id": ObjectId(chat_id)})
        if chat_doc:
            chat_doc["id"] = str(chat_doc["_id"])
            del chat_doc["_id"]
            return chat_doc
        return None

    async def delete_chat(self, chat_id: str) -> bool:
        from bson import ObjectId
        result = await self.collection.delete_one({"_id": ObjectId(chat_id)})
        return result.deleted_count > 0