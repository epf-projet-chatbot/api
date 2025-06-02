#!/usr/bin/env python3
"""
Script de test pour vérifier l'API Chatbot
"""
import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import db_manager
from app.repositories.user_repository import UserRepository
from app.models.user import UserCreate


async def test_api_setup():
    """Tester la configuration de l'API"""
    try:
        # Connecter à MongoDB
        await db_manager.connect_to_mongo()
        print("Connexion MongoDB réussie")
        
        # Créer les index
        await db_manager.create_indexes()
        print("Index MongoDB créés")
        
        # Tester le repository
        user_repo = UserRepository(db_manager.database)
        
        # Créer un utilisateur de test
        test_user = UserCreate(
            email="test@example.com",
            password="testpassword123",
            role="user"
        )
        
        # Vérifier si l'utilisateur existe déjà
        existing_user = await user_repo.get_user_by_email(test_user.email)
        if existing_user:
            print("Utilisateur de test existe déjà")
        else:
            user = await user_repo.create_user(test_user)
            print(f"Utilisateur de test créé: {user.email}")
        
        # Fermer la connexion
        await db_manager.close_mongo_connection()
        print("Configuration API testée avec succès")
        
    except Exception as e:
        print(f"Erreur lors du test: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_api_setup())
