"""
Gestionnaire de base de données MongoDB
"""
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .config import settings


class DatabaseManager:
    """Gestionnaire de connexion MongoDB"""
    
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.database: AsyncIOMotorDatabase = None
    
    async def connect_to_mongo(self):
        """Établir la connexion à MongoDB"""
        
        try:
            self.client = AsyncIOMotorClient(settings.mongodb_url)
            
            self.database = self.client[settings.database_name]
            
            # Test de connexion
            await self.client.admin.command('ping')
        except Exception as e:
            raise
    
    async def close_mongo_connection(self):
        """Fermer la connexion MongoDB"""
        if self.client:
            self.client.close()
    
    async def create_indexes(self):
        """Créer les index nécessaires"""
        
        try:
            # Index pour les utilisateurs
            await self.database.users.create_index("email", unique=True)
            
            # Index de recherche textuelle pour les documents
            await self.database.documents.create_index([
                ("content", "text"), 
                ("title", "text")
            ])
            
        except Exception as e:
            raise


# Instance globale du gestionnaire de base de données
db_manager = DatabaseManager()


def get_database() -> AsyncIOMotorDatabase:
    """Obtenir l'instance de la base de données"""
    if db_manager.database is None:
        raise RuntimeError("Database not initialized")
    return db_manager.database
