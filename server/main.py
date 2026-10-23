"""The game server: one WebSocket connection per player.

Connection:
    1. the client connects to ws://host:5001
    2. it sends, within AUTH_TIMEOUT seconds:
           {"type": "auth", "token": "<token from POST /auth/login>", "content_hash": "<optional>"}
    3. the server answers {"type": "welcome", ...}, then the stats, the inventory and the
       players around; the client asks for the items on the ground ("request_world_items") once
       its zone is loaded. From then on, any message of doc/*/websocket.md.
A refused connection gets {"type": "error", "code", "message"} and is closed."""
import asyncio
import json
import signal

import websockets

from common import db, tokens
from common.config import settings
from common.log import log
from server import content, registry, router, storage, world
from server.session import Session
import server.modules  # noqa: F401  (registers the handlers)
from server.modules import character
from server.modules.inventory import handlers as inventory

AUTH_TIMEOUT = 10.0
MAX_MESSAGE_SIZE = 64 * 1024   # bytes; a bigger message closes the connection


async def _refuse(websocket, code: str, message: str):
    try:
        await websocket.send(json.dumps({"type": "error", "code": code, "message": message}))
        await websocket.close()
    except websockets.ConnectionClosed:
        pass


async def _authenticate(websocket) -> tokens.TokenUser | None:
    try:
        message = json.loads(await asyncio.wait_for(websocket.recv(), AUTH_TIMEOUT))
    except (asyncio.TimeoutError, json.JSONDecodeError, UnicodeDecodeError, websockets.ConnectionClosed):
        await _refuse(websocket, "auth_required", "Send {\"type\": \"auth\", \"token\": ...} first")
        return None
    if not isinstance(message, dict) or message.get("type") != "auth":
        await _refuse(websocket, "auth_required", "Send {\"type\": \"auth\", \"token\": ...} first")
        return None
    user = tokens.verify(str(message.get("token", "")))
    if user is None:
        await _refuse(websocket, "invalid_token", "Invalid or expired token: log in again")
        return None
    client_hash = message.get("content_hash")
    if client_hash != content.content_hash:
        if settings().require_content_hash:
            await _refuse(websocket, "content_mismatch", "Game data differs from the server's: update the game")
            return None
        if client_hash:
            log.warning("%s has different game data (client %s, server %s)", user.username, client_hash,
                        content.content_hash)
    return user


async def _join(session: Session):
    """Loads the player and shows them the world."""
    character.load(session, await storage.load_character(session.user_id))
    inventory.load(session, await storage.load_inventory("player", session.user_id))
    session.last_worn = inventory.worn(session)
    world.players[session.user_id] = session
    await session.send({"type": "welcome", "user_id": session.user_id, "username": session.username,
                        "is_admin": session.is_admin, "server": settings().server_name,
                        "content_hash": content.content_hash, "location": session.location,
                        "position": session.position, "appearance": session.appearance})
    await character.send_stats(session)
    await inventory.send_inventory(session)
    await world.appear(session)
    for hook in world.on_join:
        await hook(session)
    log.info("%s joined (%d online)", session.username, len(world.players))


async def _leave(session: Session):
    """Hides the player, saves them, forgets them."""
    try:
        for hook in world.on_leave:
            await hook(session)
        await world.disappear(session)
    finally:
        if world.players.get(session.user_id) is session:
            del world.players[session.user_id]
        await storage.flush(session)
        session.closed.set()
        log.info("%s left (%d online)", session.username, len(world.players))


async def handle_connection(websocket):
    user = await _authenticate(websocket)
    if user is None:
        return
    previous = world.players.get(user.user_id)
    if previous is not None:
        # Same account connected again (crash, second window): the old connection is closed and
        # saved first, so the new one loads up to date data.
        await previous.error("Connected from somewhere else", "replaced")
        await previous.websocket.close()
        await previous.closed.wait()
    elif len(world.players) >= settings().server_max_players:
        await _refuse(websocket, "server_full", "The server is full")
        return

    session = Session(user.user_id, user.username, user.is_admin, websocket)
    try:
        await _join(session)
        async for message in websocket:
            await router.dispatch(session, message)
    except websockets.ConnectionClosed:
        pass
    except Exception:
        log.exception("Connection of %s failed", user.username)
    finally:
        await _leave(session)


async def main():
    config = settings()
    content.load()
    await db.connect()
    await db.migrate()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:   # Windows
            pass

    background = [asyncio.create_task(registry.heartbeat_forever(world.players)),
                  asyncio.create_task(storage.save_positions_forever(world.players))]
    background += [asyncio.create_task(task()) for task in world.tasks]
    async with websockets.serve(handle_connection, config.server_host, config.server_port,
                                max_size=MAX_MESSAGE_SIZE):
        log.info("Game server '%s' on ws://%s:%d", config.server_name, config.server_host, config.server_port)
        await stop.wait()
        log.info("Stopping: saving the players...")
        for session in list(world.players.values()):
            await session.websocket.close(1001, "Server stopping")
        for session in list(world.players.values()):
            await session.closed.wait()

    for task in background:
        task.cancel()
    await registry.unregister()
    await db.close()
