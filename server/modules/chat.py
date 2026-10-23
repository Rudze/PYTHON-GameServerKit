"""Chat: {"type": "chat", "message": "hello", "channel": "local" | "global"}.

"local" reaches the players of the same zone, "global" every connected player. Limits in
game.json "chat": max_length, per_second. Everyone, the sender included, gets:
    {"type": "chat", "channel", "user_id", "name", "message"}"""
import time

from server import content, world
from server.router import handler
from server.session import Session

CHANNELS = ("local", "global")


@handler("chat")
async def on_chat(session: Session, data: dict):
    message = data.get("message")
    channel = data.get("channel", "local")
    if not isinstance(message, str) or channel not in CHANNELS:
        return
    message = " ".join(message.split())   # no line breaks or runs of spaces
    if not message:
        return
    if len(message) > content.RULES.chat_max_length:
        await session.error(f"Message too long ({content.RULES.chat_max_length} characters max)", "chat_too_long")
        return
    now = time.monotonic()
    if now - session.last_chat_time < 1.0 / content.RULES.chat_per_second:
        await session.error("You are sending messages too fast", "chat_too_fast")
        return
    session.last_chat_time = now

    out = {"type": "chat", "channel": channel, "user_id": session.user_id, "name": session.name, "message": message}
    if channel == "global":
        await world.broadcast_all(out)
    else:
        await world.broadcast(session, out, include_self=True)
