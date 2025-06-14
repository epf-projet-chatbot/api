from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from api.schemas.chat_schema import ChatCreate, Chat as ChatSchema
from api.models.chat_model import Chat as ChatModel
from api.controllers.chat_controller import ChatController
from core.database import get_database
from core.security import get_current_active_user

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

def get_chat_controller(db=Depends(get_database)) -> ChatController:
    """Dépendance pour obtenir le contrôleur de chat"""
    controller = ChatController(db)
    return controller

@router.post("/", response_model=ChatSchema)
async def create_chat(
    data: ChatCreate, 
    controller: ChatController = Depends(get_chat_controller),
    current_user: dict = Depends(get_current_active_user)
):
    """Créer une nouvelle discussion."""
    print(f"🚀 ROUTE DEBUG: create_chat called with data: {data}")
    print(f"🚀 ROUTE DEBUG: current_user: {current_user['email']}")
    print(f"🚀 ROUTE DEBUG: controller type: {type(controller)}")
    
    # Ajouter l'user_id depuis l'utilisateur connecté
    data.user_id = current_user["_id"]
    result = await controller.create_chat(data)
    return result

@router.get("/", response_model=List[ChatSchema])
async def list_chats(
    controller: ChatController = Depends(get_chat_controller),
    current_user: dict = Depends(get_current_active_user)
):
    """Lister toutes les discussions de l'utilisateur connecté."""
    return await controller.get_all_chats(current_user["_id"])

@router.get("/debug-test")
async def test_debug():
    """Endpoint de test pour vérifier les logs"""
    return {"message": "Debug test working", "status": "ok"}

@router.get("/{chat_id}", response_model=ChatSchema)
async def get_chat(
    chat_id: str, 
    controller: ChatController = Depends(get_chat_controller),
    current_user: dict = Depends(get_current_active_user)
):
    """Récupérer une discussion par son ID (seulement si elle appartient à l'utilisateur)."""
    chat = await controller.get_chat_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Vérifier que le chat appartient à l'utilisateur connecté
    if chat.get("user_id") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return chat

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str, 
    controller: ChatController = Depends(get_chat_controller),
    current_user: dict = Depends(get_current_active_user)
):
    """Supprimer une discussion par son ID (seulement si elle appartient à l'utilisateur)."""
    # Vérifier d'abord que le chat existe et appartient à l'utilisateur
    chat = await controller.get_chat_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.get("user_id") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    success = await controller.delete_chat(chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"detail": "Deleted successfully"}
