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
    cors_origins: list[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instance globale des settings
settings = Settings()
