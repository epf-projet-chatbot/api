"""
Service pour la gestion des utilisateurs (logique métier)
"""
from typing import List, Optional
from fastapi import HTTPException, status

from api.repositories.user_repository import UserRepository
from api.models.user import UserCreate, UserUpdate, UserInDB, UserResponse
from core.security import verify_password


class UserService:
    """Service contenant la logique métier pour les utilisateurs"""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    async def get_user_by_id(self, user_id: str) -> UserInDB:
        """Récupérer un utilisateur par ID"""
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Récupérer un utilisateur par email"""
        return await self.user_repo.get_user_by_email(email)
    
    async def list_users(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[UserInDB]:
        """Lister tous les utilisateurs"""
        users = await self.user_repo.list_users(skip=skip, limit=limit)
        return users
    
    async def update_user(
        self, 
        user_id: str, 
        user_data: UserUpdate
    ) -> UserInDB:
        """
        Mettre à jour un utilisateur
        Logique métier: validation des données
        """

        existing_user = await self.user_repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user_data.email and user_data.email != existing_user.email:
            email_exists = await self.user_repo.get_user_by_email(user_data.email)
            if email_exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email déjà existant"
                )
        
        updated_user = await self.user_repo.update_user(user_id, user_data)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user"
            )
        
        return updated_user
    
    async def delete_user(self, user_id: str) -> bool:
        """Supprimer un utilisateur"""

        existing_user = await self.user_repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        success = await self.user_repo.delete_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )
        
        return True
    
    async def verify_user_password(
        self, 
        email: str, 
        password: str
    ) -> Optional[UserInDB]:
        """
        Vérifier le mot de passe d'un utilisateur
        Logique métier: authentification
        """
        user = await self.user_repo.get_user_by_email(email)
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user
    
    def user_to_response(self, user: UserInDB) -> UserResponse:
        """Convertir UserInDB en UserResponse"""
        return UserResponse(
            email=user.email,
            is_active=user.is_active,
            role=user.role,
            admin=user.admin,
            id=str(user.id),
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Changer le mot de passe d'un utilisateur
        Vérifie d'abord que le mot de passe actuel est correct
        """
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )


        user_update = UserUpdate(password=new_password)
        updated_user = await self.user_repo.update_user(user_id, user_update)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
        
        return True
