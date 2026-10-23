"""Tells the API this game server exists: it writes itself in the `servers` table at start, then
updates its player count every HEARTBEAT seconds. The API lists the servers whose last report is
recent (api/routes/servers.py); a server that crashes disappears from the list on its own."""
import asyncio

from common import db
from common.config import settings
from common.log import log

HEARTBEAT = 10.0   # seconds; the API considers a server offline after 30 s of silence


async def report(player_count: int):
    config = settings()
    await db.pool().execute("""
        INSERT INTO servers (name, host, port, max_players, current_players, last_heartbeat)
        VALUES ($1, $2, $3, $4, $5, now())
        ON CONFLICT (name) DO UPDATE SET host = EXCLUDED.host, port = EXCLUDED.port,
            max_players = EXCLUDED.max_players, current_players = EXCLUDED.current_players, last_heartbeat = now()""",
        config.server_name, config.server_public_host, config.server_port, config.server_max_players, player_count)


async def heartbeat_forever(players: dict):
    while True:
        try:
            await report(len(players))
        except Exception:
            log.exception("Server heartbeat failed")
        await asyncio.sleep(HEARTBEAT)


async def unregister():
    """On a clean stop: offline at once, without waiting for the timeout."""
    await db.pool().execute("UPDATE servers SET current_players = 0, last_heartbeat = 'epoch' WHERE name = $1",
                            settings().server_name)
