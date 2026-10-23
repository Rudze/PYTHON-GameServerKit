"""PostgreSQL access, shared by the API and the game server.

One pool of connections per process (asyncpg: fully asynchronous, nothing blocks the event loop
while a query runs). JSONB columns come back as Python dicts and lists.

    pool = await db.connect()      # at startup
    row = await db.pool().fetchrow("SELECT ...", value)
    await db.close()               # at shutdown

The schema is in migrations/*.sql: `migrate()` applies the files not applied yet, in name
order, each in a transaction, and remembers them in the schema_migrations table."""
import json
from pathlib import Path

import asyncpg

from common.config import settings
from common.log import log

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"

_pool: asyncpg.Pool | None = None


async def _init_connection(connection: asyncpg.Connection):
    # JSONB <-> Python objects, without an extra json.dumps / json.loads in every query
    await connection.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def connect() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        config = settings()
        _pool = await asyncpg.create_pool(config.database_url, min_size=config.db_pool_min,
                                          max_size=config.db_pool_max, init=_init_connection)
    return _pool


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not connected: call db.connect() at startup")
    return _pool


async def close():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def migrate():
    """Applies the migrations/*.sql files not applied yet. Safe to call at every start, from
    several processes at once (an advisory lock lets one apply them, the others wait)."""
    async with pool().acquire() as connection:
        await connection.execute("SELECT pg_advisory_lock(726354)")
        try:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name       TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )""")
            done = {row["name"] for row in await connection.fetch("SELECT name FROM schema_migrations")}
            for path in sorted(MIGRATIONS.glob("*.sql")):
                if path.name in done:
                    continue
                async with connection.transaction():
                    await connection.execute(path.read_text(encoding="utf-8"))
                    await connection.execute("INSERT INTO schema_migrations (name) VALUES ($1)", path.name)
                log.info("Migration applied: %s", path.name)
        finally:
            await connection.execute("SELECT pg_advisory_unlock(726354)")
