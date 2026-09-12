import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from bson.objectid import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from backend.app.database import get_db

security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Securely hash a plain password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def create_access_token(user_id: str, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token with subject as string user ID."""
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def format_user_doc(user_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to convert MongoDB user document into safe dict format matching UserResponse."""
    return {
        "id": str(user_doc["_id"]),
        "full_name": user_doc["full_name"],
        "email": user_doc["email"],
        "mobile": user_doc["mobile"],
        "is_active": user_doc.get("is_active", True),
        "created_at": user_doc.get("created_at")
    }

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Dependency to extract and validate JWT token, returning current MongoDB user doc."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session has expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise credentials_exception

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    try:
        query_filter = {"_id": ObjectId(user_id_str)}
    except Exception:
        query_filter = {"_id": user_id_str}

    user = db.users.find_one(query_filter)
    if not user:
        try:
            user = db.users.find_one({"id": int(user_id_str)})
        except Exception:
            pass

    if not user or not user.get("is_active", True):
        raise credentials_exception

    return user
