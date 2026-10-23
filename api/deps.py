"""What the routes share: the user of the request, read from its "Authorization: Bearer <token>"."""
from fastapi import Header, HTTPException, status

from common import tokens


def current_user(authorization: str = Header(default="")) -> tokens.TokenUser:
    scheme, _, token = authorization.partition(" ")
    user = tokens.verify(token) if scheme == "Bearer" and token else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})
    return user
