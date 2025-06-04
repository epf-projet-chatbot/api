"""
Modèles Pydantic pour les utilisateurs
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    """Classe pour gérer les ObjectId MongoDB avec Pydantic"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema, handler):
        field_schema.update(type="string")


class UserBase(BaseModel):
    """Schéma de base pour un utilisateur"""
    email: EmailStr
    is_active: bool = True
    role: str = "user"


class UserCreate(UserBase):
    """Schéma pour la création d'un utilisateur"""
    password: str = Field(..., min_length=6, description="Mot de passe (minimum 6 caractères)")


class UserUpdate(BaseModel):
    """Schéma pour la mise à jour d'un utilisateur"""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
    is_active: Optional[bool] = None
    role: Optional[str] = None


class UserInDB(UserBase):
    """Schéma pour un utilisateur en base de données"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
    }


class UserResponse(UserBase):
    """Schéma de réponse pour un utilisateur"""
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            ObjectId: str
        }
    }


class Token(BaseModel):
    """Schéma pour les tokens d'authentification"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schéma pour les données du token"""
    user_id: Optional[str] = None