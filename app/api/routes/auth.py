"""
Routes d'authentification
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from api.models.user import UserCreate, UserResponse, Token
from api.services.auth_service import AuthService
from api.repositories.user_repository import UserRepository
from core.database import get_database
from core.security import get_current_active_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_user_repository(db=Depends(get_database)) -> UserRepository:
    """Dépendance pour obtenir le repository utilisateur"""
    return UserRepository(db)


def get_auth_service(user_repo: UserRepository = Depends(get_user_repository)) -> AuthService:
    """Dépendance pour obtenir le service d'authentification"""
    return AuthService(user_repo)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Enregistrer un nouvel utilisateur"""
    user = await auth_service.register_user(user_data)
    return UserResponse(
        email=user.email,
        is_active=user.is_active,
        role=user.role,
        id=str(user.id),
        created_at=user.created_at
    )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Connexion utilisateur"""
    return await auth_service.authenticate_user(form_data.username, form_data.password)


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_active_user)):
    """Récupérer les informations de l'utilisateur connecté"""
    return UserResponse(
        email=current_user["email"],
        is_active=current_user.get("is_active", True),
        role=current_user.get("role", "user"),
        id=current_user["_id"],
        created_at=current_user.get("created_at")
    )