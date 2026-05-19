from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

try:
    from .config import JWT_SECRET_KEY, JWT_ALGORITHM
except ImportError:
    from config import JWT_SECRET_KEY, JWT_ALGORITHM

# tokenUrl is only used for OpenAPI docs — this service does not issue tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=True)


def decode_access_token(token: str) -> Optional[str]:
    """
    Decodes a JWT issued by the main backend and returns user_id.

    NOTE: This service never issues tokens. It only validates them.
    The token must be signed with the same JWT_SECRET_KEY as the main backend.

    Customize the payload field name here if your main backend
    uses a different field (e.g. "sub" instead of "user_id").
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")  # TODO: change field name if needed
        if user_id is None:
            return None
        return str(user_id)
    except JWTError:
        return None


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency — returns authenticated user_id or raises 401."""
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
