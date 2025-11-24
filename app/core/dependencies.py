"""
Dépendances centralisées pour FastAPI
"""
from typing import Generator
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.database import get_database
from core.security import get_current_active_user
from api.repositories.user_repository import UserRepository
from api.repositories.chat_repository import ChatRepository
from api.repositories.message_repository import MessageRepository
from api.repositories.template_repository import TemplateRepository
from api.repositories.upload_repository import UploadRepository


# ==================== DATABASE DEPENDENCIES ====================

def get_db() -> AsyncIOMotorDatabase:
    """Récupérer la connexion à la base de données"""
    return get_database()


# ==================== REPOSITORY DEPENDENCIES ====================

def get_user_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> UserRepository:
    """Dépendance pour obtenir le repository utilisateur"""
    return UserRepository(db)


def get_chat_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> ChatRepository:
    """Dépendance pour obtenir le repository chat"""
    return ChatRepository(db)


def get_message_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> MessageRepository:
    """Dépendance pour obtenir le repository message"""
    return MessageRepository(db)


def get_template_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> TemplateRepository:
    """Dépendance pour obtenir le repository template"""
    return TemplateRepository(db)


def get_upload_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> UploadRepository:
    """Dépendance pour obtenir le repository upload"""
    return UploadRepository(db)


# ==================== SERVICE DEPENDENCIES ====================

def get_auth_service(user_repo: UserRepository = Depends(get_user_repository)):
    """Dépendance pour obtenir le service d'authentification"""
    from api.services.auth_service import AuthService
    return AuthService(user_repo)


def get_user_service(user_repo: UserRepository = Depends(get_user_repository)):
    """Dépendance pour obtenir le service utilisateur"""
    from api.services.user_service import UserService
    return UserService(user_repo)


def get_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    message_repo: MessageRepository = Depends(get_message_repository),
    upload_repo: UploadRepository = Depends(get_upload_repository)
):
    """Dépendance pour obtenir le service chat"""
    from api.services.chat_service import ChatService
    return ChatService(chat_repo, message_repo, upload_repo)


def get_message_service(
    message_repo: MessageRepository = Depends(get_message_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """Dépendance pour obtenir le service message"""
    from api.services.message_service import MessageService
    return MessageService(message_repo, chat_repo)


def get_upload_service(
    upload_repo: UploadRepository = Depends(get_upload_repository),
    message_repo: MessageRepository = Depends(get_message_repository)
):
    """Dépendance pour obtenir le service upload"""
    from api.services.upload_service import UploadService
    return UploadService(upload_repo, message_repo)


def get_template_service(template_repo: TemplateRepository = Depends(get_template_repository)):
    """Dépendance pour obtenir le service template"""
    from api.services.template_service import TemplateService
    return TemplateService(template_repo)


# ==================== AUTH DEPENDENCIES ====================

async def get_current_user(user: dict = Depends(get_current_active_user)) -> dict:
    """Récupérer l'utilisateur actuellement connecté"""
    return user
