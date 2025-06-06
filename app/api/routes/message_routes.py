from fastapi import APIRouter, HTTPException
from typing import List
from bson import ObjectId

from ..controllers.message_controllers import get_all_messages, get_message, create_message, delete_message
from ..schemas.message_schemas import MessageSchema

router = APIRouter(
    prefix="/messages",
    tags=["Messages"]
)

@router.get("/", response_model=None)
async def fetch_all_messages():
    try:
        messages = await get_all_messages()
        if not messages:
            raise HTTPException(status_code=404, detail="Aucun message trouvé")
        return messages
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{message_id}", response_model=None)
async def fetch_message(message_id: str):
    try:
        message = await get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail=f"Message avec l'ID {message_id} non trouvé")
        return message
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/", response_model=None)
async def create_messages(message: MessageSchema):
    try:
        message_id = await create_message(
            discussion=ObjectId(message.discussion_id),
            content=message.content,
            attachments=message.attachments
        )
        return {"message_id": message_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreuuur lors de la création du message: {str(e)}")

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
        