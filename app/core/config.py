"""
Configuration de l'application
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration de l'application"""
    
    # Configuration de l'application
    app_name: str = "Chatbot API"
    debug: bool = False
    version: str = "1.0.0"
    
    # Configuration MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "chatbot"
    
    # Configuration JWT
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Configuration CORS
    cors_origins: list[str] = ["http://localhost:3000"]
    
    # Configuration des fichiers
    base_url: str = "http://localhost:8000"  # URL de base de l'API
    # Configuration de l'environnement
    environment: str = "development"  # "development" ou "production"
    
    @property
    def is_production(self) -> bool:
        """Vérifie si on est en production"""
        return self.environment.lower() == "production"
    
    @property
    def cookie_secure(self) -> bool:
        """Détermine si les cookies doivent être sécurisés"""
        return self.is_production
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instance globale des settings
settings = Settings()
