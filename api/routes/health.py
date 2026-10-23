"""Is the API up, and can it reach the database? (for a load balancer, Docker, monitoring)"""
from fastapi import APIRouter, Response, status

from common import db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(response: Response):
    try:
        await db.pool().fetchval("SELECT 1")
        return {"status": "ok"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "database unreachable"}
