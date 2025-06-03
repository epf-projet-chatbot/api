"""
Service d'authentification
"""
from datetime import timedelta
from typing import Optional
from fastapi import HTTPException, status
from repositories.user_repository import UserRepository
from models.user import UserCreate, UserInDB, Token
from core.security import create_access_token
from core.config import settings


class AuthService:
    """Service pour l'authentification et la gestion des utilisateurs"""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def register_user(self, user_data: UserCreate) -> UserInDB:
        """Enregistrer un nouvel utilisateur"""
        # Vérifier si l'utilisateur existe déjà
        existing_user = await self.user_repository.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Créer l'utilisateur
        return await self.user_repository.create_user(user_data)
    
    async def authenticate_user(self, email: str, password: str) -> Token:
        """Authentifier un utilisateur et retourner un token"""
        user = await self.user_repository.authenticate_user(email, password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        # Créer le token d'accès
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        
        return Token(access_token=access_token, token_type="bearer")
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Récupérer un utilisateur par son ID"""
        return await self.user_repository.get_user_by_id(user_id)
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Récupérer un utilisateur par son email"""
        return await self.user_repository.get_user_by_email(email)
