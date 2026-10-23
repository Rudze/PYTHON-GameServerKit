"""The HTTP API: accounts and the list of game servers.

Run (from the project root):  python -m api
Interactive documentation once running: http://127.0.0.1:8000/docs"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from api.routes import auth, servers, health
from common import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    await db.migrate()
    yield
    await db.close()


VERSION = (Path(__file__).resolve().parent.parent / "VERSION").read_text().strip()   # written by semantic-release

app = FastAPI(title="Game Server Kit API", version=VERSION, lifespan=lifespan)
app.include_router(auth.router)
app.include_router(servers.router)
app.include_router(health.router)
