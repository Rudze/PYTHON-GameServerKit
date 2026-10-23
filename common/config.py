"""Settings of the API and of the game server, read from the environment (or a .env file at the
root of the project). See .env.example for the list.

Each process asks only for what it needs: `settings()` returns everything, and a missing value
fails at startup with a clear message instead of later, in the middle of a request."""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable {name} (see .env.example)")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str          # postgresql://user:password@host:5432/database
    db_pool_min: int
    db_pool_max: int
    jwt_secret: str
    jwt_expire_seconds: int
    api_host: str
    api_port: int
    server_host: str
    server_port: int
    server_name: str           # how this game server appears in the server list
    server_public_host: str    # the address the clients use to reach it
    server_max_players: int
    data_dir: Path             # game data: items.json, game.json
    require_content_hash: bool # refuse clients whose game data differs from the server's
    autosave_delay: float      # seconds between a change and its save (changes in between are grouped)


@lru_cache
def settings() -> Settings:
    return Settings(
        database_url=_required("DATABASE_URL"),
        db_pool_min=int(os.getenv("DB_POOL_MIN", "2")),
        db_pool_max=int(os.getenv("DB_POOL_MAX", "10")),
        jwt_secret=_required("JWT_SECRET"),
        jwt_expire_seconds=int(os.getenv("JWT_EXPIRE_SECONDS", "86400")),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        server_host=os.getenv("SERVER_HOST", "0.0.0.0"),
        server_port=int(os.getenv("SERVER_PORT", "5001")),
        server_name=os.getenv("SERVER_NAME", "main"),
        server_public_host=os.getenv("SERVER_PUBLIC_HOST", "127.0.0.1"),
        server_max_players=int(os.getenv("SERVER_MAX_PLAYERS", "100")),
        data_dir=Path(os.getenv("DATA_DIR", str(ROOT / "data"))),
        require_content_hash=os.getenv("REQUIRE_CONTENT_HASH", "false").lower() == "true",
        autosave_delay=float(os.getenv("AUTOSAVE_DELAY", "2.0")),
    )
