from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database import get_database
from core.dependencies import get_current_user
from api.models.user import UserInDB
from api.repositories.user_repository import UserRepository
from api.repositories.chat_repository import ChatRepository
from api.repositories.message_repository import MessageRepository
from rag.embedding import get_all_corrections, delete_correction_from_chroma

router = APIRouter(prefix="/admin", tags=["admin"])

async def verify_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    return current_user

@router.get("/users")
async def get_all_users(
    database: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(verify_admin)
):
    user_repo = UserRepository(database)
    users = await user_repo.get_all_users()
    return [{
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "is_active": user.is_active
    } for user in users]

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    database: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(verify_admin)
):
    if user_id == str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas supprimer votre propre compte"
        )
    
    user_repo = UserRepository(database)
    success = await user_repo.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    return {"message": "Utilisateur supprimé avec succès"}

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str,
    database: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(verify_admin)
):
    if role not in ["user", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rôle invalide. Valeurs acceptées : user, admin"
        )
    
    if user_id == str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas modifier votre propre rôle"
        )
    
    user_repo = UserRepository(database)
    user = await user_repo.update_user_role(user_id, role)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role
    }

@router.get("/corrections")
async def get_all_corrections_route(
    current_user: dict = Depends(verify_admin)
):
    try:
        corrections = get_all_corrections()
        return corrections
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des corrections: {str(e)}"
        )

@router.delete("/corrections/{correction_id}")
async def delete_correction(
    correction_id: str,
    current_user: dict = Depends(verify_admin)
):
    try:
        success = delete_correction_from_chroma(correction_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Correction non trouvée"
            )
        
        return {"message": "Correction supprimée avec succès"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression: {str(e)}"
        )

@router.get("/stats")
async def get_admin_stats(
    database: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(verify_admin)
):
    user_repo = UserRepository(database)
    
    total_users = await user_repo.count_users()
    print(f"[DEBUG] Total users from DB: {total_users}")
    
    try:
        corrections = get_all_corrections()
        total_corrections = len(corrections)
        print(f"[DEBUG] Total corrections from Chroma: {total_corrections}")
        print(f"[DEBUG] Corrections: {corrections}")
    except Exception as e:
        print(f"[DEBUG] Error getting corrections: {e}")
        total_corrections = 0
    
    return {
        "total_users": total_users,
        "total_corrections": total_corrections
    }
