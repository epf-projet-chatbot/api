from fastapi import APIRouter, HTTPException
from typing import List
from bson import ObjectId
from bson.errors import InvalidId

from rag.answer import generate_answer
from ..controllers.message_controllers import get_all_messages_by_chat, get_message, create_message, delete_message, get_conversation_history
from ..schemas.message_schemas import MessageCreate, BotQuery, BotQueryWithHistory

router = APIRouter(
    prefix="/messages",
    tags=["Messages"]
)

@router.get("/{discussion_id}", response_model=None)
async def fetch_all_messages_by_chat(discussion_id: str):
    try:
        if not discussion_id:
            raise HTTPException(status_code=400, detail="L'ID de la discussion est requis") 
        messages = await get_all_messages_by_chat(discussion_id)
        # Retourner une liste vide au lieu d'une erreur si aucun message
        return messages if messages else []
    except InvalidId:
        raise HTTPException(status_code=400, detail="Format d'ID de discussion invalide")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/single/{message_id}", response_model=None)
async def fetch_message(message_id: str):
    try:
        message = await get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail=f"Message avec l'ID {message_id} non trouvé")
        return message
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/", response_model=None)
async def create_messages(message: MessageCreate):
    try:
        message_id = await create_message(
            discussion=ObjectId(message.discussion_id),
            content=message.content,
            role=message.role,  
            attachments=message.attachments  
        )
        return {"message_id": message_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création du message: {str(e)}")



@router.post("/{discussion_id}/chatbot", response_model=None)
async def create_bot_message(discussion_id: str, payload: BotQuery):
    try:
        query = payload.query
        if not discussion_id or not query:
            raise HTTPException(status_code=400, detail="L'ID de la discussion et le contenu sont requis")

        conversation_history = await get_conversation_history(discussion_id, limit=10)
        response, sources, template_path = generate_answer(query, conversation_history)
        
        # Préparer les pièces jointes si un template est détecté
        attachments = []
        if template_path:
            import os
            from urllib.parse import quote
            from core.config import settings
            filename = os.path.basename(template_path)
            
            # Encoder le nom du fichier pour l'URL 
            encoded_filename = quote(filename)
            
            file_url = f"{settings.base_url}/templates/{encoded_filename}"
            
            attachments.append({
                "filename": filename, 
                "url": file_url  
            })
        
        message_id = await create_message(
            discussion=ObjectId(discussion_id),
            content=response,
            role="bot",
            attachments=attachments if attachments else None
        )
        
        return {
            "message_id": message_id, 
            "response": response,
            "sources": sources,
            "used_history": len(conversation_history) > 0,
            "attachments": attachments if attachments else None
        }
    except InvalidId:
        raise HTTPException(status_code=400, detail="Format d'ID de discussion invalide")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création du message du bot: {str(e)}")
    

@router.delete("/{message_id}", response_model=None)
async def delete_messages(message: str):
    try:
        message_id= ObjectId(message)
        msg=await delete_message(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail=f"Message avec l'ID {message_id} non trouvé")
        return {"message": f"Message avec l'ID {message_id} supprimé avec succès"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression du message: {str(e)}")


@router.get("/{discussion_id}/history", response_model=None)
async def get_chat_history(discussion_id: str, limit: int = 10):
    """
    Récupérer l'historique des messages d'une conversation
    Args:
        discussion_id: ID de la discussion
        limit: Nombre maximum de messages à récupérer (défaut: 10)
    """
    try:
        if not discussion_id:
            raise HTTPException(status_code=400, detail="L'ID de la discussion est requis")
        
        # Valider la limite
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="La limite doit être entre 1 et 100")
        
        history = await get_conversation_history(discussion_id, limit=limit)
        return {
            "discussion_id": discussion_id,
            "history": history,
            "count": len(history)
        }
    except InvalidId:
        raise HTTPException(status_code=400, detail="Format d'ID de discussion invalide")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération de l'historique: {str(e)}")
