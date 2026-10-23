"""Access tokens (JWT, HS256), made by the API at login and checked by the game server when a
client connects. Both read the same JWT_SECRET.

Payload: {"sub": "<user id>", "username": ..., "is_admin": bool, "exp": ...}"""
import time
from dataclasses import dataclass

import jwt

from common.config import settings

ALGORITHM = "HS256"


@dataclass(frozen=True)
class TokenUser:
    user_id: int
    username: str
    is_admin: bool


def create(user_id: int, username: str, is_admin: bool = False) -> str:
    payload = {"sub": str(user_id), "username": username, "is_admin": is_admin,
               "exp": int(time.time()) + settings().jwt_expire_seconds}
    return jwt.encode(payload, settings().jwt_secret, algorithm=ALGORITHM)


def verify(token: str) -> TokenUser | None:
    """The user of a valid token, None if it is invalid or expired."""
    try:
        payload = jwt.decode(token, settings().jwt_secret, algorithms=[ALGORITHM])
        return TokenUser(int(payload["sub"]), payload["username"], bool(payload.get("is_admin", False)))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
