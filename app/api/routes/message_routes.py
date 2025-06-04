from fastapi import APIRouter, HTTPException
from typing import List

from ..controllers.message_controllers import message_controller
from ..schemas.message_schemas import MessageSchema

router = APIRouter(
    prefix="/messages",
    tags=["Messages"]
)

@router.get("/", response_model=List[MessageSchema])
async def get_all_messages():
    messages = await message_controller.get_all_messages()
    if not messages:
        raise HTTPException(status_code=404, detail="Aucun message trouvé")
    return messages