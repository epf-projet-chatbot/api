from fastapi import APIRouter, HTTPException, Depends
from typing import List
from bson import ObjectId
from bson.errors import InvalidId

from rag.answer import generate_answer
from api.services.message_service import MessageService
from api.schemas.message_schemas import MessageCreate, BotQuery
from core.dependencies import get_message_service
from core.config import settings

router = APIRouter(
    prefix="/messages",
    tags=["Messages"]
)

@router.get("/{discussion_id}", response_model=None)
async def fetch_all_messages_by_chat(
    discussion_id: str,
    message_service: MessageService = Depends(get_message_service)
):
    """Récupérer tous les messages d'un chat"""
    if not discussion_id:
        raise HTTPException(status_code=400, detail="L'ID de la discussion est requis")
    
    messages = await message_service.get_chat_messages(discussion_id)
    return messages if messages else []

@router.get("/single/{message_id}", response_model=None)
async def fetch_message(
    message_id: str,
    message_service: MessageService = Depends(get_message_service)
):
    """Récupérer un message par son ID"""
    message = await message_service.get_message_by_id(message_id)
    return message
    
@router.post("/", response_model=None)
async def create_messages(
    message: MessageCreate,
    message_service: MessageService = Depends(get_message_service)
):
    """Créer un nouveau message"""
    message_id = await message_service.create_message(message)
    return {"message_id": message_id}



@router.post("/{discussion_id}/chatbot", response_model=None)
async def create_bot_message(
    discussion_id: str, 
    payload: BotQuery,
    message_service: MessageService = Depends(get_message_service)
):
    """Créer un message bot avec réponse RAG"""
    query = payload.query
    if not discussion_id or not query:
        raise HTTPException(status_code=400, detail="L'ID de la discussion et le contenu sont requis")

    # Récupérer l'historique via le service
    conversation_history = await message_service.get_conversation_history(discussion_id, limit=10)
    
    # Générer la réponse avec RAG
    response, sources, template_path = generate_answer(query, conversation_history)
    
    # Préparer les pièces jointes si un template est détecté
    attachments = []
    if template_path:
        import os
        from urllib.parse import quote
        filename = os.path.basename(template_path)
        encoded_filename = quote(filename)
        file_url = f"{settings.base_url}/templates/{encoded_filename}"
        
        attachments.append({
            "filename": filename, 
            "url": file_url  
        })
    
    # Créer le message bot via MessageCreate
    from api.schemas.message_schemas import MessageCreate
    bot_message = MessageCreate(
        discussion_id=discussion_id,
        content=response,
        role="bot",
        attachments=attachments if attachments else None
    )
    
    message_id = await message_service.create_message(bot_message)
    
    return {
        "message_id": message_id, 
        "response": response,
        "sources": sources,
        "used_history": len(conversation_history) > 0,
        "attachments": attachments if attachments else None
    }
    

@router.delete("/{message_id}", response_model=None)
async def delete_messages(
    message_id: str,
    message_service: MessageService = Depends(get_message_service)
):
    """Supprimer un message"""
    await message_service.delete_message(message_id)
    return {"message": f"Message avec l'ID {message_id} supprimé avec succès"}


@router.get("/{discussion_id}/history", response_model=None)
async def get_chat_history(
    discussion_id: str, 
    limit: int = 10,
    message_service: MessageService = Depends(get_message_service)
):
    """Récupérer l'historique des messages d'une conversation"""
    if not discussion_id:
        raise HTTPException(status_code=400, detail="L'ID de la discussion est requis")
    
    history = await message_service.get_conversation_history(discussion_id, limit=limit)
    return {
        "discussion_id": discussion_id,
        "history": history,
        "count": len(history)
    }
