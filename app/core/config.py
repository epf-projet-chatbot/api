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
    database_name: str = "chatbot_db"
    
    # Configuration JWT
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Configuration CORS
    cors_origins: str = "https://badinter.epfprojets.com,http://badinter.epfprojets.com,badinter.epfprojets.com,https://api.badinter.epfprojets.com,http://api.badinter.epfprojets.com,http://badinter-projet.epfprojets.com,https://badinter-projet.epfprojets.com"
    
    @property 
    def cors_origins_list(self) -> list[str]:
        """Retourne la liste des origines CORS"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins
    
    
    # Configuration des fichiers
    base_url: str = "https://api.badinter.epfprojets.com"  # URL de base de l'API
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
