"""
Application FastAPI principale pour le Chatbot API
"""
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings
from core.database import db_manager, get_database
from core.security import get_current_active_user

from api.routes import auth_router, chat_router, message_router

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire de cycle de vie de l'application"""
    print("Starting application lifespan...")
    
    # Startup avec retries pour MongoDB
    import asyncio
    max_retries = 10
    retry_delay = 2
    
    print(f"Configuration loaded:")
    print(f"   - MongoDB URL: {settings.mongodb_url}")
    print(f"   - Database: {settings.database_name}")
    print(f"   - App Name: {settings.app_name}")
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_retries}: Connecting to MongoDB...")
            await db_manager.connect_to_mongo()
            
            print(f"🔄 Attempt {attempt + 1}/{max_retries}: Creating indexes...")
            await db_manager.create_indexes()
            
            print("Application started successfully")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                print(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"Startup error after {max_retries} attempts: {e}")
                raise
    
    print("🎯 Lifespan startup completed, yielding control...")
    yield
    
    # Shutdown
    print("Starting application shutdown...")
    await db_manager.close_mongo_connection()
    print("Application shutdown complete")


# Création de l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    description="API pour le chatbot juridique avec authentification MongoDB",
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(message_router)

# Routes de base
@app.get("/", tags=["Root"])
async def read_root():
    """Route de base pour vérifier que l'API fonctionne"""
    return {
        "message": f"Bienvenue sur {settings.app_name}",
        "version": settings.version,
        "status": "running"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Vérification de santé de l'API et de MongoDB"""
    logger.info("🏥 HEALTH CHECK: Endpoint called!")
    try:
        # Test de connexion MongoDB simple et efficace
        if db_manager.database is None:
            raise RuntimeError("Database not connected")
        
        # Test simple avec list_collection_names() qui fonctionne toujours
        collections = await db_manager.database.list_collection_names()
        logger.info(f"🏥 HEALTH CHECK: Found {len(collections)} collections")
        
        return {
            "status": "healthy", 
            "database": "connected",
            "version": settings.version,
            "database_name": db_manager.database.name,
            "collections_count": len(collections)
        }
    except Exception as e:
        logger.error(f"🏥 HEALTH CHECK ERROR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )


@app.get("/protected", tags=["Test"])
async def protected_route(current_user: dict = Depends(get_current_active_user)):
    """Route protégée pour tester l'authentification"""
    return {
        "message": "Cette route est protégée",
        "user": {
            "id": current_user["_id"],
            "email": current_user["email"],
            "role": current_user.get("role", "user")
        }
    }



# Point d'entrée pour le développement
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )