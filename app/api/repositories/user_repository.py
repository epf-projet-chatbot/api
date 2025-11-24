"""
Repository pour la gestion des utilisateurs en MongoDB
"""
from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from api.models.user import UserCreate, UserUpdate, UserInDB
from core.security import get_password_hash, verify_password


class UserRepository:
    """Repository pour les opérations CRUD sur les utilisateurs"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.collection = database.users
    
    async def create_indexes(self):
        """Créer les index nécessaires"""
        await self.collection.create_index("email", unique=True)
        await self.collection.create_index("created_at")
    
    async def create_user(self, user_data: UserCreate) -> UserInDB:
        """Créer un nouvel utilisateur"""
        default_name = user_data.email.split('@')[0] if '@' in user_data.email else user_data.email
        
        user_dict = {
            "email": user_data.email,
            "name": user_data.name or default_name,
            "hashed_password": get_password_hash(user_data.password),
            "is_active": user_data.is_active,
            "role": user_data.role,
            "admin": user_data.admin,
            "created_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id
        return UserInDB(**user_dict)
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Récupérer un utilisateur par son ID"""
        user_doc = await self.collection.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            return UserInDB(**user_doc)
        return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Récupérer un utilisateur par son email"""
        user_doc = await self.collection.find_one({"email": email})
        if user_doc:
            return UserInDB(**user_doc)
        return None
    
    async def update_user(self, user_id: str, update_data: dict = None, user_data: UserUpdate = None) -> Optional[UserInDB]:
        """Mettre à jour un utilisateur
        
        Args:
            user_id: ID de l'utilisateur
            update_data: Dictionnaire de données à mettre à jour (prend la priorité)
            user_data: Objet UserUpdate (pour compatibilité)
        """
        fields_to_update = {}
        
        if update_data:
            fields_to_update = update_data.copy()
            if "password" in fields_to_update:
                fields_to_update["hashed_password"] = get_password_hash(fields_to_update.pop("password"))
        elif user_data:
            if user_data.email is not None:
                fields_to_update["email"] = user_data.email
            if user_data.password is not None:
                fields_to_update["hashed_password"] = get_password_hash(user_data.password)
            if user_data.is_active is not None:
                fields_to_update["is_active"] = user_data.is_active
            if user_data.role is not None:
                fields_to_update["role"] = user_data.role
            if user_data.admin is not None:
                fields_to_update["admin"] = user_data.admin
            
        if fields_to_update:
            fields_to_update["updated_at"] = datetime.utcnow()
            result = await self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": fields_to_update}
            )
            if result.modified_count:
                return await self.get_user_by_id(user_id)
        return None
    
    async def delete_user(self, user_id: str) -> bool:
        """Supprimer un utilisateur"""
        result = await self.collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0
    
    async def list_users(self, skip: int = 0, limit: int = 100) -> List[UserInDB]:
        """Lister les utilisateurs avec pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        users = []
        async for user_doc in cursor:
            users.append(UserInDB(**user_doc))
        return users
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        """Authentifier un utilisateur"""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    async def get_all_users(self) -> List[UserInDB]:
        """Récupérer tous les utilisateurs"""
        cursor = self.collection.find().sort("created_at", -1)
        users = []
        async for user_doc in cursor:
            users.append(UserInDB(**user_doc))
        return users
    
    async def update_user_role(self, user_id: str, role: str) -> Optional[UserInDB]:
        """Mettre à jour le rôle d'un utilisateur"""
        return await self.update_user(user_id, update_data={"role": role})
    
    async def count_users(self) -> int:
        """Compter le nombre total d'utilisateurs"""
        return await self.collection.count_documents({})
