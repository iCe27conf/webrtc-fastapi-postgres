import time
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# Why: Strong hashing and signed tokens are essential for auth in production.
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(sub: str, expires_minutes: int | None = None) -> str:
    payload = {
        "sub": sub,
        "iat": int(time.time()),
        "exp": int(time.time()) + 60 * (expires_minutes or settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user_id(creds: HTTPAuthorizationCredentials | None = Depends(security)) -> int:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = decode_token(creds.credentials)
    return int(data["sub"])  # user id