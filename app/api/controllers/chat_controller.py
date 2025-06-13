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
            chat_object_id = ObjectId(chat_id)
            
            print(f"🗑️ Starting cascade deletion for chat: {chat_id}")
            
            # 1. Vérifier que le chat existe et appartient à l'utilisateur
            chat_doc = await self.collection.find_one({
                "_id": chat_object_id,
                "user_id": user_id
            })
            
            if not chat_doc:
                print(f"❌ Chat {chat_id} not found or doesn't belong to user {user_id}")
                return False
            
            # 3. Supprimer tous les fichiers associés aux messages du chat
            files_deleted = await self._delete_chat_files(chat_id)
            print(f"🗑️ Deleted {files_deleted} files")
            
            # 2. Supprimer tous les messages associés au chat
            messages_deleted = await self._delete_chat_messages(chat_id)
            print(f"🗑️ Deleted {messages_deleted} messages")
            
            
            
            # 4. Supprimer le chat lui-même
            result = await self.collection.delete_one({"_id": chat_object_id})
            chat_deleted = result.deleted_count > 0
            
            if chat_deleted:
                print(f"✅ Chat {chat_id} and all associated data deleted successfully")
            else:
                print(f"❌ Failed to delete chat {chat_id}")
            
            return chat_deleted
            
        except Exception as e:
            print(f"❌ Error during cascade deletion: {str(e)}")
            return False

    async def _delete_chat_messages(self, chat_id: str) -> int:
        """
        Supprimer tous les messages d'un chat
        """
        try:
            # Supprimer tous les messages avec discussion_id = chat_id
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
            
            # 1. Récupérer tous les messages du chat pour trouver les attachments
            cursor = self.database.messages.find({"discussion_id": ObjectId(chat_id)})
            print(f"🔍 Starting file deletion for chat: {chat_id}")
            
            file_ids_to_delete = []
            message_count = 0
            
            async for message in cursor:
                message_count += 1
                print(f"🔍 Processing message {message_count}: {message.get('_id')}")
                print(f"🔍 Message content: {message.get('content', 'No content')[:100]}...")
                
                if "attachments" in message and message["attachments"]:
                    print(f"🔍 Found {len(message['attachments'])} attachments in message")
                    for i, attachment in enumerate(message["attachments"]):
                        print(f"🔍 Attachment {i+1}: {attachment}")
                        # Extraire l'ID du fichier depuis l'URL
                        if "url" in attachment:
                            url = attachment["url"]
                            print(f"🔍 Processing attachment URL: {url}")
                            if "/upload/gridfs/" in url:
                                # Fichier GridFS
                                file_id = url.split("/upload/gridfs/")[-1]
                                file_ids_to_delete.append(("gridfs", file_id))
                                print(f"📁 Found GridFS file to delete: {file_id}")
                            elif "/files/gridfs/" in url:
                                # Fichier GridFS (ancien format)
                                file_id = url.split("/files/gridfs/")[-1]
                                file_ids_to_delete.append(("gridfs", file_id))
                                print(f"📁 Found GridFS file to delete (legacy): {file_id}")
                            elif "/files/" in url:
                                # Fichier système de fichiers
                                filename = url.split("/files/")[-1]
                                file_ids_to_delete.append(("filesystem", filename))
                                print(f"📁 Found filesystem file to delete: {filename}")
                        else:
                            print(f"⚠️ Attachment has no URL: {attachment}")
                else:
                    print(f"🔍 No attachments found in message {message.get('_id')}")
            
            print(f"🔍 Processed {message_count} messages, found {len(file_ids_to_delete)} files to delete")
            
            # 2. Supprimer les fichiers GridFS
            gridfs_bucket = AsyncIOMotorGridFSBucket(self.database, bucket_name="files")
            for storage_type, file_id in file_ids_to_delete:
                try:
                    if storage_type == "gridfs":
                        print(f"🗑️ Attempting to delete GridFS file: {file_id}")
                        await gridfs_bucket.delete(ObjectId(file_id))
                        deleted_count += 1
                        print(f"✅ Deleted GridFS file: {file_id}")
                    elif storage_type == "filesystem":
                        # Supprimer le fichier du système de fichiers
                        import os
                        file_path = f"uploads/{file_id}"
                        print(f"🗑️ Attempting to delete filesystem file: {file_path}")
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_count += 1
                            print(f"✅ Deleted filesystem file: {file_path}")
                        
                        # Supprimer les métadonnées du fichier
                        print(f"🗑️ Deleting metadata for file: {file_id}")
                        result = await self.database.uploads.delete_many({"filename": file_id})
                        print(f"🗑️ Deleted {result.deleted_count} metadata records for file: {file_id}")
                        
                except Exception as e:
                    print(f"❌ Error deleting file {file_id}: {str(e)}")
                    continue
            
            print(f"🔍 Total files deleted: {deleted_count}")
            return deleted_count
            
        except Exception as e:
            print(f"❌ Error deleting chat files: {str(e)}")
            return 0