"""The game servers a client can join. A server registers itself and reports its player count
every few seconds (server/registry.py); one silent for HEARTBEAT_TIMEOUT seconds is offline."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.deps import current_user
from common import db

router = APIRouter(prefix="/servers", tags=["servers"])

HEARTBEAT_TIMEOUT = 30   # seconds


class ServerOut(BaseModel):
    name: str
    host: str
    port: int
    region: str
    current_players: int
    max_players: int


_ONLINE = f"""
    SELECT name, host, port, region, current_players, max_players FROM servers
    WHERE last_heartbeat > now() - interval '{HEARTBEAT_TIMEOUT} seconds'
      AND current_players < max_players
    ORDER BY current_players::float / greatest(max_players, 1), name
"""


@router.get("", response_model=list[ServerOut], dependencies=[Depends(current_user)])
async def list_servers():
    """The online servers that are not full, the least loaded first."""
    return [ServerOut(**dict(row)) for row in await db.pool().fetch(_ONLINE)]


@router.get("/best", response_model=ServerOut, dependencies=[Depends(current_user)])
async def best_server():
    """The least loaded online server (what a "Play" button needs)."""
    row = await db.pool().fetchrow(_ONLINE + " LIMIT 1")
    if row is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No server available")
    return ServerOut(**dict(row))
