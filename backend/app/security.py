import datetime
from typing import Optional, Dict, Any
import bcrypt
import jwt
from fastapi import HTTPException, status
from backend.app.config import settings


def get_password_hash(password: str) -> str:
    """Hashes a password using direct bcrypt library."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Creates a signed JWT with expiration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_access_token(user_id: int, role: str) -> str:
    """Creates a standard access token with sub, role, type: access."""
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access"
    }
    return create_token(payload, datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_reset_token(user_id: int, hashed_password: str) -> str:
    """
    Creates a password reset JWT containing a password fingerprint.
    When password is changed, the fingerprint changes, rendering old tokens invalid.
    """
    fp = hashed_password[-10:] if len(hashed_password) >= 10 else hashed_password
    payload = {
        "sub": str(user_id),
        "type": "reset",
        "fp": fp
    }
    return create_token(payload, datetime.timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES))


def decode_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
