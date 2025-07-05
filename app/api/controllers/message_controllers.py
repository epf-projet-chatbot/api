from api.models.message_models import Message
from bson import ObjectId
from bson.errors import InvalidId
from core.database import get_database
from datetime import datetime
from typing import List


def generate_chat_title(first_message: str, max_length: int = 50) -> str:
    """
    Génère un titre de chat basé sur le premier message de l'utilisateur
    """
    # Nettoyer le message
    title = first_message.strip()
    
    # Si le message est trop long, le tronquer
    if len(title) > max_length:
        title = title[:max_length-3] + "..."
    
    # Si le message est vide ou trop court, utiliser un titre par défaut
    if len(title) < 3:
        title = "Nouvelle discussion"
    
    return title

async def update_chat_title_if_first_user_message(discussion_id: str, content: str):
    """
    Met à jour le titre du chat avec le premier message utilisateur si c'est le cas
    """
    from api.repositories.chat_repository import ChatRepository
    
    db = get_database()
    print(f"🔍 Vérification de la mise à jour du titre pour discussion: {discussion_id}")
    
    # Vérifier s'il y a déjà des messages utilisateur dans cette discussion
    existing_user_messages = await db.messages.count_documents({
        "discussion_id": ObjectId(discussion_id),
        "role": "user"
    })
    
    print(f"📊 Nombre de messages utilisateur existants: {existing_user_messages}")
    
    # Si c'est le premier message utilisateur (count = 1), mettre à jour le titre
    if existing_user_messages == 1:
        chat_repo = ChatRepository(db)
        new_title = generate_chat_title(content)
        
        print(f"🎯 Mise à jour du titre vers: '{new_title}'")
        result = await chat_repo.update_chat(discussion_id, {"topic": new_title})
        
        if result:
            print(f"✅ Titre du chat mis à jour avec succès: '{new_title}'")
        else:
            print(f"❌ Échec de la mise à jour du titre")
    else:
        print(f"⏭️ Pas le premier message utilisateur, titre non modifié")


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
        message_id = str(cursor.inserted_id)
        
        # Si c'est un message utilisateur, vérifier si le titre du chat doit être mis à jour
        if role == "user":
            await update_chat_title_if_first_user_message(str(discussion), content)
        
        return message_id
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

async def get_conversation_history(discussion_id: str, limit: int = 10) -> List[dict]:
    """
    Récupère l'historique des messages d'une conversation
    Args:
        discussion_id: ID de la discussion
        limit: Nombre maximum de messages récents à récupérer (par défaut 10)
    Returns:
        Liste des messages triés par date de création (plus anciens en premier)
    """
    db = get_database()
    try:
        discussion_obj_id = ObjectId(discussion_id)
        
        # Récupérer les messages triés par date de création (plus récents d'abord)
        cursor = db.messages.find(
            {"discussion_id": discussion_obj_id}
        ).sort("date_created", -1).limit(limit)
        
        messages = []
        async for msg in cursor:
            # Simplifier le message pour le contexte
            simplified_msg = {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "date_created": msg.get("date_created")
            }
            messages.append(simplified_msg)
        
        # Inverser pour avoir les plus anciens en premier
        messages.reverse()
        return messages
    
    except InvalidId:
        raise ValueError(f"Invalid ObjectId format for discussion_id: {discussion_id}")
    except Exception as e:
        raise ValueError(f"Error fetching conversation history: {str(e)}")