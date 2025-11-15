"""
Routes d'authentification
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from api.models.user import UserCreate, UserResponse, Token
from api.services.auth_service import AuthService
from api.repositories.user_repository import UserRepository
from core.config import settings


from core.dependencies import get_auth_service, get_user_repository, get_current_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Enregistrer un nouvel utilisateur"""
    user = await auth_service.register_user(user_data)
    return UserResponse(
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        role=user.role,
        id=str(user.id),
        created_at=user.created_at
    )


@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Connexion utilisateur avec cookie httpOnly"""    
    try:
        # Authentifier l'utilisateur
        token_data = await auth_service.authenticate_user(form_data.username, form_data.password)
        
        # Récupérer les infos utilisateur pour la réponse
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
        
        
        return {
            "message": "Connexion réussie",
            "user": {
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "admin": user.admin,
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
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Récupérer les informations de l'utilisateur connecté"""
    return UserResponse(
        email=current_user["email"],
        name=current_user.get("name"),
        is_active=current_user.get("is_active", True),
        role=current_user.get("role", "user"),
        admin=current_user.get("admin", False),
        id=current_user["_id"],
        created_at=current_user.get("created_at")
    )


@router.put("/me/password", status_code=status.HTTP_200_OK)
async def change_user_password(
    password_data: dict,
    current_user: dict = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Changer le mot de passe de l'utilisateur connecté"""
    from api.services.user_service import UserService
    
    if "current_password" not in password_data or "new_password" not in password_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="current_password and new_password are required"
        )
    
    if password_data["current_password"] == password_data["new_password"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    user_service = UserService(user_repo)
    await user_service.change_password(
        user_id=current_user["_id"],
        current_password=password_data["current_password"],
        new_password=password_data["new_password"]
    )
    
    return {"message": "Password updated successfully"}


@router.patch("/me/profile", status_code=status.HTTP_200_OK)
async def update_user_profile(
    profile_data: dict,
    current_user: dict = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Mettre à jour le profil de l'utilisateur connecté (nom complet)"""
    from api.models.user import UserProfileUpdate
    
    if "name" not in profile_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name field is required"
        )
    
    name = profile_data["name"].strip()
    if not name or len(name) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name must not be empty"
        )
    
    if len(name) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name must not exceed 100 characters"
        )
    
    # Mettre à jour le nom dans la base de données
    updated_user = await user_repo.update_user(
        user_id=current_user["_id"],
        update_data={"name": name}
    )
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "message": "Profile updated successfully",
        "name": name
    }