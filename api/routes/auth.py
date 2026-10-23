"""Accounts: create one, log in (get a token), read your own account."""
import asyncio
import re

import asyncpg
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from api.deps import current_user
from api.ratelimit import limit
from common import db, tokens
from common.config import settings
from common.log import log

router = APIRouter(prefix="/auth", tags=["auth"])

USERNAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterBody(BaseModel):
    username: str = Field(examples=["player_one"])
    email: str = Field(examples=["player@example.com"])
    password: str = Field(min_length=8, max_length=72, examples=["a long password"])   # bcrypt reads 72 bytes

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        if not USERNAME.match(value):
            raise ValueError("3 to 20 letters, digits or _")
        return value

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        if not EMAIL.match(value) or len(value) > 254:
            raise ValueError("invalid email")
        return value.lower()


class LoginBody(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool


class LoginOut(BaseModel):
    token: str
    expires_in: int
    user: UserOut


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut,
             dependencies=[Depends(limit(5, 60))])
async def register(body: RegisterBody):
    # bcrypt is slow on purpose: in a thread, the other requests do not wait
    password_hash = await asyncio.to_thread(_hash, body.password)
    try:
        row = await db.pool().fetchrow(
            "INSERT INTO users (username, email, password_hash) VALUES ($1, $2, $3) RETURNING id, username, is_admin",
            body.username, body.email, password_hash)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username or email already used")
    log.info("Account created: %s", body.username)
    return UserOut(**dict(row))


@router.post("/login", response_model=LoginOut, dependencies=[Depends(limit(10, 60))])
async def login(body: LoginBody):
    row = await db.pool().fetchrow(
        "SELECT id, username, password_hash, is_admin FROM users WHERE lower(username) = lower($1)", body.username)
    if row is None or not await asyncio.to_thread(_check, body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    await db.pool().execute("UPDATE users SET last_login_at = now() WHERE id = $1", row["id"])
    return LoginOut(token=tokens.create(row["id"], row["username"], row["is_admin"]),
                    expires_in=settings().jwt_expire_seconds,
                    user=UserOut(id=row["id"], username=row["username"], is_admin=row["is_admin"]))


@router.get("/me", response_model=UserOut)
async def me(user: tokens.TokenUser = Depends(current_user)):
    return UserOut(id=user.user_id, username=user.username, is_admin=user.is_admin)
