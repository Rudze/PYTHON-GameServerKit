"""How the characters move, and going from zone to zone.

The client sends its state often while the character moves:
    {"type": "state", "location": "forest", "x": 1.0, "y": 0.0, "z": 3.5, "rot": 1.57, ...}
The fields are those of game.json "movement": numbers (clamped to their limit), flags
(booleans) and texts (short strings). x, y, z and rot are also kept as the player's position,
saved for their next connection. The others get {"type": "player_state", "user_id", "state"}.

The server relays and keeps the state; it does not simulate physics. A game that needs
anti-cheat on movement checks the speed here (see doc/*/extending.md)."""
import math
import time

from server import content, world
from server.router import handler
from server.session import Session

POSITION_KEYS = ("x", "y", "z", "rot")


def read_state(data: dict) -> dict | None:
    """The state fields of a message, checked and clamped. None if a number is missing or wrong."""
    rules = content.RULES
    state = {}
    for key, limit in rules.state_numbers.items():
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        state[key] = max(-limit, min(limit, float(value)))
    for key in rules.state_flags:
        state[key] = data.get(key) is True
    for key, length in rules.state_texts.items():
        value = data.get(key, "")
        state[key] = value if isinstance(value, str) and len(value) <= length else ""
    return state


@handler("state")
async def on_state(session: Session, data: dict):
    if data.get("location") != session.location:
        return   # sent from the previous zone, just before a travel
    now = time.monotonic()
    if now - session.last_state_time < 1.0 / content.RULES.states_per_second:
        return
    state = read_state(data)
    if state is None:
        return
    session.last_state_time = now
    session.state = state
    if all(key in state for key in POSITION_KEYS):
        session.position = {key: state[key] for key in POSITION_KEYS}
        session.position_dirty = True
    await world.broadcast(session, {"type": "player_state", "user_id": session.user_id, "state": state})


@handler("travel")
async def on_travel(session: Session, data: dict):
    """{"location"}: goes to another zone (a portal, a menu). Refused when game.json
    "zones.client_travel" is false: then only the server moves players (world.send_to)."""
    if not content.RULES.client_travel:
        await session.error("Travel is decided by the server", "travel_refused")
        return
    location = data.get("location")
    if location != session.location:
        await world.send_to(session, location)
