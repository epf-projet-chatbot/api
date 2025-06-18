from bson import ObjectId
from api.schemas.chat_schema import ChatCreate, ChatUpdate
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket


class ChatController:
    """Contrôleur pour la gestion des chats"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.chats

    async def create_chat(self, data: ChatCreate) -> Dict[str, Any]:
        from datetime import datetime
        
        chat_dict = data.model_dump()
        
        # S'assurer que les champs obligatoires sont initialisés
        if "topic" not in chat_dict or chat_dict["topic"] is None:
            chat_dict["topic"] = "Nouvelle discussion"
            
        chat_dict["created_at"] = datetime.utcnow()
        chat_dict["updated_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(chat_dict)
        
        inserted_doc = await self.collection.find_one({"_id": result.inserted_id})
        
        if inserted_doc:
            # Convertir directement l'ObjectId en string
            inserted_doc["id"] = str(inserted_doc["_id"])
            del inserted_doc["_id"]
            return inserted_doc
        else:
            return chat_dict

    async def get_all_chats(self, user_id: str) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"user_id": user_id})
        chats = []
        async for chat_doc in cursor:
            # Convertir directement les ObjectId en string
            chat_doc["id"] = str(chat_doc["_id"])
            del chat_doc["_id"]
            
            # Convertir user_id si c'est un ObjectId
            if "user_id" in chat_doc and isinstance(chat_doc["user_id"], ObjectId):
                chat_doc["user_id"] = str(chat_doc["user_id"])
            
            # S'assurer que les champs obligatoires existent avec des valeurs par défaut
            if "messages" not in chat_doc or chat_doc["messages"] is None:
                chat_doc["messages"] = []
            if "topic" not in chat_doc or chat_doc["topic"] is None:
                chat_doc["topic"] = "Nouvelle discussion"
                
            chats.append(chat_doc)
        return chats

    async def get_chat_by_id(self, chat_id: str) -> Optional[Dict[str, Any]]:
        from bson import ObjectId
        chat_doc = await self.collection.find_one({"_id": ObjectId(chat_id)})
        if chat_doc:
            chat_doc["id"] = str(chat_doc["_id"])
            del chat_doc["_id"]
            return chat_doc
        return None

    async def delete_chat(self, chat_id: str, user_id: str) -> bool:
        """
        Supprimer un chat et tous ses documents associés (suppression en cascade)
        """
        from bson import ObjectId
        
        try:
            # Valider l'ObjectId
            if not ObjectId.is_valid(chat_id):
                return False
                
            chat_object_id = ObjectId(chat_id)
            
            # vérifier que le chat existe et appartient à l'utilisateur
            chat_doc = await self.collection.find_one({
                "_id": chat_object_id,
                "user_id": user_id
            })
            
            if not chat_doc:
                return False
            
            # supprimer tous les fichiers associés aux messages du chat
            files_deleted = await self._delete_chat_files(chat_id)            
            # supprimer tous les messages associés au chat
            messages_deleted = await self._delete_chat_messages(chat_id)            
            # supprimer le chat lui-même
            result = await self.collection.delete_one({"_id": chat_object_id})
            chat_deleted = result.deleted_count > 0
            
            return chat_deleted
            
        except Exception as e:
            print(f"❌ Error in delete_chat: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def _delete_chat_messages(self, chat_id: str) -> int:
        """
        Supprimer tous les messages d'un chat
        """
        try:
            # suprimer tous les messages avec discussion_id = chat_id
            result = await self.database.messages.delete_many({
                "discussion_id": ObjectId(chat_id)
            })
            return result.deleted_count
            
        except Exception as e:
            print(f"❌ Error deleting messages: {str(e)}")
            return 0

    async def _delete_chat_files(self, chat_id: str) -> int:
        """
        Supprimer tous les fichiers associés à un chat
        """
        try:
            deleted_count = 0
            cursor = self.database.messages.find({"discussion_id": ObjectId(chat_id)})
            
            file_ids_to_delete = []
            message_count = 0
            
            async for message in cursor:
                message_count += 1
                if "attachments" in message and message["attachments"]:
                    for i, attachment in enumerate(message["attachments"]):
                        # extraire l'ID du fichier depuis l'URL
                        if "url" in attachment:
                            url = attachment["url"]
                            if "/upload/gridfs/" in url:
                                #fichier GridFS
                                file_id = url.split("/upload/gridfs/")[-1]
                                file_ids_to_delete.append(("gridfs", file_id))
                            elif "/files/gridfs/" in url:
                                # Fichier GridFS (ancien format)
                                file_id = url.split("/files/gridfs/")[-1]
                                file_ids_to_delete.append(("gridfs", file_id))
                            elif "/files/" in url:
                                # fichier système de fichiers
                                filename = url.split("/files/")[-1]
                                file_ids_to_delete.append(("filesystem", filename))
                        else:
                            print(f"⚠️ Attachment has no URL: {attachment}")
                else:
                    print(f"🔍 No attachments found in message {message.get('_id')}")
            
            # supprimer les fichiers GridFS
            gridfs_bucket = AsyncIOMotorGridFSBucket(self.database, bucket_name="files")
            for storage_type, file_id in file_ids_to_delete:
                try:
                    if storage_type == "gridfs":
                        await gridfs_bucket.delete(ObjectId(file_id))
                        deleted_count += 1
                    elif storage_type == "filesystem":
                        # Supprimer le fichier du système de fichiers
                        import os
                        file_path = f"uploads/{file_id}"
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_count += 1
                        
                        # spprimer les métadonnées du fichier
                        result = await self.database.uploads.delete_many({"filename": file_id})
                        
                except Exception as e:
                    print(f"Error deleting file {file_id}: {str(e)}")
                    continue
            
            print(f"Total files deleted: {deleted_count}")
            return deleted_count
            
        except Exception as e:
            print(f"Error deleting chat files: {str(e)}")
            return 0