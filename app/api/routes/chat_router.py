from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from api.schemas.chat_schema import ChatCreate, Chat as ChatSchema
from api.services.chat_service import ChatService
from core.dependencies import get_chat_service, get_current_user

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

@router.post("/", response_model=ChatSchema)
async def create_chat(
    data: ChatCreate, 
    chat_service: ChatService = Depends(get_chat_service),
    current_user: dict = Depends(get_current_user)
):
    """Créer une nouvelle discussion."""
    result = await chat_service.create_chat(data, current_user["_id"])
    return result

@router.get("/", response_model=List[ChatSchema])
async def list_chats(
    chat_service: ChatService = Depends(get_chat_service),
    current_user: dict = Depends(get_current_user)
):
    """Lister toutes les discussions de l'utilisateur connecté."""
    return await chat_service.get_user_chats(current_user["_id"])

@router.get("/debug-test")
async def test_debug():
    """Endpoint de test pour vérifier les logs"""
    return {"message": "Debug test working", "status": "ok"}

@router.get("/{chat_id}", response_model=ChatSchema)
async def get_chat(
    chat_id: str, 
    chat_service: ChatService = Depends(get_chat_service),
    current_user: dict = Depends(get_current_user)
):
    """Récupérer une discussion par son ID (seulement si elle appartient à l'utilisateur)."""
    # Le service gère déjà la vérification de propriété
    chat = await chat_service.get_chat_by_id(chat_id, current_user["_id"])
    return chat

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str, 
    chat_service: ChatService = Depends(get_chat_service),
    current_user: dict = Depends(get_current_user)
):
    """Supprimer une discussion par son ID (seulement si elle appartient à l'utilisateur)."""
    # Le service gère déjà toutes les validations et la suppression en cascade
    success = await chat_service.delete_chat(chat_id, current_user["_id"])
    return {"detail": "Chat deleted successfully"}
