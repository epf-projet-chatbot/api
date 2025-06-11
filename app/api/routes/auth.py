"""
Routes d'authentification
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from api.models.user import UserCreate, UserResponse, Token
from api.services.auth_service import AuthService
from api.repositories.user_repository import UserRepository
from core.database import get_database
from core.security import get_current_active_user
from core.config import settings


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


@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Connexion utilisateur avec cookie httpOnly"""    
    try:
        # Authentifier l'utilisateur
        token_data = await auth_service.authenticate_user(form_data.username, form_data.password)
        
        # Récupérer les infos utilisateur pour la réponse
        user_repo = UserRepository(get_database())
        user = await user_repo.get_user_by_email(form_data.username)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur non trouvé"
            )
        
        # httpOnly - ne pas ajouter de guillemets automatiques
        response.set_cookie(
            key="access_token",
            value=token_data.access_token,  # token sans "Bearer "
            httponly=True,      
            secure=False,  # A CHANGER EN TRUE QUAND ON SERA EN PROD  
            samesite="lax",     
            max_age=1800,
            path="/", 
        )
        
        print(f"🍪 Cookie défini: access_token = {token_data.access_token[:20]}...")
        
        return {
            "message": "Connexion réussie",
            "user": {
                "email": user.email,
                "role": user.role,
                "id": str(user.id),
                "is_active": user.is_active
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect"
        )

# ----------------------------------------------------------------- A Supprimer------------------------------------------------
@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Récupérer tous les utilisateurs (sans authentification)"""
    users = await user_repo.list_users(skip=skip, limit=limit)
    return [
        UserResponse(
            email=user.email,
            is_active=user.is_active,
            role=user.role,
            id=str(user.id),
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        for user in users
    ]
# -----------------------------------------------------------------------------------------------------------------

@router.post("/logout")
async def logout(response: Response):
    """Déconnexion - supprimer le cookie"""
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=False, 
        samesite="lax"
    )
    return {"message": "Déconnexion réussie"}


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