"""
Repository pour la gestion des templates en base de données
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase


class TemplateRepository:
    """Repository pour les opérations CRUD sur les templates"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.templates
    
    async def create(self, template_data: dict) -> Dict[str, Any]:
        """Créer un nouveau template"""
        template_data["created_at"] = datetime.utcnow()
        template_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(template_data)
        template_doc = await self.collection.find_one({"_id": result.inserted_id})
        
        if template_doc:
            template_doc["id"] = str(template_doc["_id"])
            del template_doc["_id"]
        return template_doc
    
    async def get_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer un template par son ID"""
        try:
            template_doc = await self.collection.find_one({"_id": ObjectId(template_id)})
            if template_doc:
                template_doc["id"] = str(template_doc["_id"])
                del template_doc["_id"]
                return template_doc
            return None
        except InvalidId:
            return None
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupérer tous les templates"""
        cursor = self.collection.find().skip(skip).limit(limit)
        templates = []
        async for template_doc in cursor:
            template_doc["id"] = str(template_doc["_id"])
            del template_doc["_id"]
            templates.append(template_doc)
        return templates
    
    async def update(self, template_id: str, template_data: dict) -> Optional[Dict[str, Any]]:
        """Mettre à jour un template"""
        try:
            template_data["updated_at"] = datetime.utcnow()
            
            result = await self.collection.update_one(
                {"_id": ObjectId(template_id)},
                {"$set": template_data}
            )
            
            if result.modified_count > 0:
                return await self.get_by_id(template_id)
            return None
        except InvalidId:
            return None
    
    async def delete(self, template_id: str) -> bool:
        """Supprimer un template"""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(template_id)})
            return result.deleted_count > 0
        except InvalidId:
            return False
    
    async def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Trouver un template par nom"""
        template_doc = await self.collection.find_one({"name": name})
        if template_doc:
            template_doc["id"] = str(template_doc["_id"])
            del template_doc["_id"]
            return template_doc
        return None
