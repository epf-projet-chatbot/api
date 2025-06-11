"""
Utilitaires de sécurité et authentification
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from fastapi.security.base import SecurityBase
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from .config import settings
from .database import get_database
from bson import ObjectId


class OAuth2PasswordBearerCookie(SecurityBase):
    """OAuth2 avec support des cookies ET headers pour FastAPI docs"""
    
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        scopes: Optional[dict] = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl, "scopes": scopes})
        super().__init__()  # SecurityBase n'accepte pas d'arguments
        self.model = {"type": "oauth2", "flows": flows}
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error

    async def __call__(self, request: Request) -> Optional[str]:
        # Essayer d'abord l'Authorization header (pour FastAPI docs)
        authorization = request.headers.get("Authorization")
        scheme, credentials = get_authorization_scheme_param(authorization)
        
        if authorization and scheme.lower() == "bearer":
            return credentials
        
        # Puis essayer le cookie (pour l'app)
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            # Nettoyer le cookie - enlever les guillemets
            cleaned_token = cookie_token.strip('"\'')
            # Le cookie contient maintenant directement le token JWT
            return cleaned_token
        
        if self.auto_error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None


# Configuration du hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration de l'authentification Bearer avec cookies
oauth2_scheme = OAuth2PasswordBearerCookie(tokenUrl="/auth/login-token")

# Configuration de l'authentification Bearer classique
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifier un mot de passe"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hasher un mot de passe"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Créer un token JWT"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """Vérifier un token JWT et retourner l'ID utilisateur"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        return user_id
    except JWTError:
        return None


async def get_current_user(
    request: Request,
    db = Depends(get_database)
) -> dict:
    """Récupérer l'utilisateur actuel à partir du token JWT (cookie ou header)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = None
    
    # Essayer d'abord l'Authorization header
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        print(f"🔍 Token from header: {token[:20]}...")
    else:
        # Puis essayer le cookie
        cookie_token = request.cookies.get("access_token")
        print(f"🔍 Cookie found: {cookie_token[:50] if cookie_token else 'None'}...")
        
        if cookie_token:
            # Nettoyer le cookie et l'utiliser directement (plus de "Bearer ")
            token = cookie_token.strip('"\'')
            print(f"🔍 Token from cookie: {token[:20]}...")
    
    if not token:
        print("🔍 No token found in header or cookie")
        raise credentials_exception
    
    # Vérifier le token
    user_id = verify_token(token)
    print(f"🔍 Token verification result: {user_id}")
    
    if user_id is None:
        print("🔍 Token verification failed")
        raise credentials_exception
    
    # Récupérer l'utilisateur depuis MongoDB
    try:
        # Le token contient l'ID utilisateur, pas l'email
        if not ObjectId.is_valid(user_id):
            print(f"🔍 Invalid ObjectId: {user_id}")
            raise credentials_exception
            
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user is None:
            print(f"🔍 User not found for ID: {user_id}")
            raise credentials_exception
        
        print(f"🔍 User found: {user['email']}")
        # Convertir ObjectId en string pour la sérialisation
        user["_id"] = str(user["_id"])
        return user
        
    except Exception as e:
        print(f"🔍 Database error: {e}")
        raise credentials_exception


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Récupérer l'utilisateur actuel actif"""
    if not current_user.get("is_active", True):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
