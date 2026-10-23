"""Which function answers which message.

A module declares its messages with the @handler decorator:

    @handler("chat")
    async def on_chat(session, data): ...

    @handler("set_name", out_of_world=True)   # also accepted in the character creator
    async def on_set_name(session, data): ...

Every message is a JSON object with a "type". The router refuses unknown types, messages sent
out of the world (unless allowed), and floods: a client gets MESSAGES_PER_SECOND messages per
second on average, up to BURST at once."""
import json
import time

from common.log import log
from server.session import Session

MESSAGES_PER_SECOND = 30.0
BURST = 60.0

_handlers: dict[str, tuple] = {}   # type -> (function, allowed out of the world)


def handler(message_type: str, out_of_world: bool = False):
    def register(function):
        if message_type in _handlers:
            raise ValueError(f"Two handlers for '{message_type}'")
        _handlers[message_type] = (function, out_of_world)
        return function
    return register


def _allowed(session: Session) -> bool:
    now = time.monotonic()
    session.message_budget = min(BURST, session.message_budget + (now - session.last_message_time) * MESSAGES_PER_SECOND)
    session.last_message_time = now
    if session.message_budget < 1.0:
        return False
    session.message_budget -= 1.0
    return True


async def dispatch(session: Session, raw: str | bytes):
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        await session.error("Invalid message", "invalid_json")
        return
    if not isinstance(data, dict):
        await session.error("Invalid message", "invalid_json")
        return
    message_type = data.get("type")
    if message_type == "ping":
        await session.send({"type": "pong", "time": data.get("time")})
        return
    if not _allowed(session):
        return   # flooding: dropped silently
    entry = _handlers.get(message_type)
    if entry is None:
        await session.error(f"Unknown message type: {message_type}", "unknown_type")
        return
    function, out_of_world = entry
    if not session.in_world and not out_of_world:
        return
    try:
        await function(session, data)
    except Exception:
        log.exception("Handler '%s' failed for %s", message_type, session.username)
        await session.error("Server error", "server_error")
