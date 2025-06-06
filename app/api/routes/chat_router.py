from fastapi import APIRouter, HTTPException, Depends
from typing import List

from api.schemas.chat_schema import ChatCreate, Chat as ChatSchema
from api.models.chat_model import Chat as ChatModel
from api.controllers.chat_controller import ChatController
from core.database import get_database

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

def get_chat_controller(db=Depends(get_database)) -> ChatController:
    """Dépendance pour obtenir le contrôleur de chat"""
    print(f"🔧 DEPENDENCY: get_chat_controller called with db: {db}")
    controller = ChatController(db)
    print(f"🔧 DEPENDENCY: created controller: {controller}")
    return controller

@router.post("/", response_model=ChatSchema)
async def create_chat(data: ChatCreate, controller: ChatController = Depends(get_chat_controller)):
    """Créer une nouvelle discussion."""
    print(f"🚀 ROUTE DEBUG: create_chat called with data: {data}")
    print(f"🚀 ROUTE DEBUG: controller type: {type(controller)}")
    result = await controller.create_chat(data)
    print(f"🚀 ROUTE DEBUG: controller returned: {result}")
    return result

@router.get("/", response_model=List[ChatSchema])
async def list_chats(controller: ChatController = Depends(get_chat_controller)):
    """Lister toutes les discussions."""
    return await controller.get_all_chats()

@router.get("/debug-test")
async def test_debug():
    """Endpoint de test pour vérifier les logs"""
    print("🧪 TEST DEBUG: This endpoint was called!")
    return {"message": "Debug test working", "status": "ok"}

@router.get("/{chat_id}", response_model=ChatSchema)
async def get_chat(chat_id: str, controller: ChatController = Depends(get_chat_controller)):
    """Récupérer une discussion par son ID."""
    chat = await controller.get_chat_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@router.delete("/{chat_id}")
async def delete_chat(chat_id: str, controller: ChatController = Depends(get_chat_controller)):
    """Supprimer une discussion par son ID."""
    success = await controller.delete_chat(chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"detail": "Deleted successfully"}