from fastapi import APIRouter, HTTPException, Depends
from typing import List
from bson import ObjectId
from bson.errors import InvalidId

from rag.answer import generate_answer
from api.services.message_service import MessageService
from api.schemas.message_schemas import MessageCreate, BotQuery, BotQueryWithHistory
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
    payload: BotQueryWithHistory,
    message_service: MessageService = Depends(get_message_service)
):
    """Créer un message bot avec réponse RAG"""
    query = payload.query
    system_prompt = payload.system_prompt
    history_limit = payload.history_limit or 10
    user_id = payload.user_id 

    
    if not discussion_id or not query:
        raise HTTPException(status_code=400, detail="L'ID de la discussion et le contenu sont requis")

    if user_id:
        correction_result = await message_service.handle_admin_correction(
            user_id=user_id,
            message_content=query,
            discussion_id=discussion_id
        )
        
        
        if correction_result:
            if "error" in correction_result:
                return {
                    "message_id": None,
                    "response": "Vous n'êtes pas autorisé à utiliser cette commande. \nSi vous pensez que c'est une erreur, veuillez contacter un administrateur",
                    "sources": [],
                    "used_history": False,
                    "is_correction": True
                }

            return {
                "message_id": None,
                "response": f"{correction_result['message']}\n\nCorrection ajoutée : {correction_result['correction']}",
                "sources": [],
                "used_history": False,
                "is_correction": True
            }

    conversation_history = await message_service.get_conversation_history(discussion_id, limit=history_limit)
    
    response, sources, template_path = generate_answer(query, conversation_history, system_prompt)

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
