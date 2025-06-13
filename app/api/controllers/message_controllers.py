from api.models.message_models import Message
from bson import ObjectId
from bson.errors import InvalidId
from core.database import get_database
from datetime import datetime
from typing import List


async def get_all_messages_by_chat(discussion:str):
    db = get_database()
    try:
        discussion_id = ObjectId(discussion)
        cursor = db.messages.find({"discussion_id": discussion_id})
        messages= []
        async for msg in cursor:
            msg["_id"] = str(msg["_id"])
            if "discussion_id" in msg:
                msg["discussion_id"] = str(msg["discussion_id"])
            messages.append(msg)
        return messages
    except InvalidId:
        raise ValueError(f"Invalid ObjectId format for discussion_id: {discussion}")
    except Exception as e:
        raise ValueError(f"Error fetching messages: {str(e)}")


async def get_message(message: str):
    db=get_database()
    try:
        message_id=ObjectId(message)
        cursor=await db.messages.find_one({"_id": message_id})
    except InvalidId:
        raise ValueError(f"Invalid ObjectId format for message_id: {message_id}")
    if cursor:
        cursor["_id"] = str(cursor["_id"])
        return cursor
    else:
        raise ValueError(f"Message with id {message_id} not found")

async def create_message(discussion: str, content: str, role: str = "user", attachments: List[dict] = None):
    db = get_database()
    try:
        discussion_id = ObjectId(discussion)
        message_data = {
            "discussion_id": discussion_id,
            "content": content,
            "role": role,
            "date_created": datetime.now()
        }
        if attachments:
            # Convertir complètement en types Python natifs
            attachment_dicts = []
            for attachment in attachments:
                if hasattr(attachment, 'dict'):  # Si c'est un objet Pydantic
                    attachment_dict = attachment.dict()
                    # Convertir HttpUrl en string
                    if 'url' in attachment_dict and hasattr(attachment_dict['url'], '__str__'):
                        attachment_dict['url'] = str(attachment_dict['url'])
                    attachment_dicts.append(attachment_dict)
                else:  # Si c'est déjà un dictionnaire
                    # S'assurer que l'URL est une string
                    if 'url' in attachment and hasattr(attachment['url'], '__str__'):
                        attachment['url'] = str(attachment['url'])
                    attachment_dicts.append(attachment)
            message_data["attachments"] = attachment_dicts
        else:
            message_data["attachments"] = []
        
        cursor = await db.messages.insert_one(message_data)
        return str(cursor.inserted_id)
    except Exception as e:
        raise ValueError(f"Error creating message: {str(e)}")
    
async def delete_message(message: str):
    db = get_database()
    try:
        message_id = ObjectId(message)
        result = await db.messages.delete_one({"_id": message_id})
        if result.deleted_count == 0:
            raise ValueError(f"Message with id {message_id} not found")
        return {"message": "Message deleted successfully"}
    except InvalidId:
        raise ValueError(f"Invalid ObjectId format for message_id: {message_id}")
    except Exception as e:
        raise ValueError(f"Error deleting message: {str(e)}")