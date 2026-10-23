"""Who is connected, who is where, who sees whom.

The world is split in zones ("locations": a map, an instance, a dungeon...). Players see and
hear only the players of their zone. A player out of the world (in the character creator, a
menu) is seen by nobody.

Hooks: a module can react to players coming and going without touching this file:

    world.on_join.append(my_function)    # async my_function(session): after the player arrived
    world.on_leave.append(my_function)   # async my_function(session): before the player is saved
    world.tasks.append(my_loop)          # async my_loop(): runs in the background while the server runs"""
import re

from server import content
from server.session import Session

LOCATION_ID = re.compile(r"^[A-Za-z0-9_:\-]{1,64}$")

players: dict[int, Session] = {}   # user id -> connected player
on_join: list = []
on_leave: list = []
tasks: list = []


def find(name_or_username: str) -> Session | None:
    """A connected player by character name or account name (any case)."""
    wanted = (name_or_username or "").lower()
    return next((p for p in players.values() if wanted in (p.name.lower(), p.username.lower())), None)


def at(location: str | None) -> list[Session]:
    """The players in the world in a zone."""
    return [p for p in players.values() if p.in_world and p.location == location]


def others(session: Session) -> list[Session]:
    """The players who see `session`: in the world, in the same zone, not themselves."""
    if not session.in_world:
        return []
    return [p for p in at(session.location) if p is not session]


async def broadcast(session: Session, message: dict, include_self: bool = False):
    """Sends a message to the players who see `session` (and to them if include_self)."""
    for other in others(session):
        await other.send(message)
    if include_self:
        await session.send(message)


async def broadcast_all(message: dict):
    """Sends a message to every connected player (server announcements...)."""
    for player in list(players.values()):
        await player.send(message)


async def appear(session: Session):
    """The player shows up in their zone: the others see them, they see the others."""
    if not session.in_world:
        return
    for other in others(session):
        await session.send({"type": "player_joined", **other.public()})
        await other.send({"type": "player_joined", **session.public()})


async def disappear(session: Session):
    """The player leaves their zone (or the world) for the others."""
    for other in others(session):
        await other.send({"type": "player_left", "user_id": session.user_id})


def is_location(location) -> bool:
    if not isinstance(location, str) or not LOCATION_ID.match(location):
        return False
    return not content.RULES.locations or location in content.RULES.locations


async def send_to(session: Session, location: str, position: dict | None = None) -> bool:
    """Moves a player to a zone, at `position` ({"x", "y", "z", "rot"}) or at its spawn (None).
    The client loads the zone when it gets "change_location". Use this for portals, teleports,
    admin commands: it is the only way a player changes zone."""
    if not is_location(location):
        await session.error("Unknown location", "unknown_location")
        return False
    from server import storage
    await disappear(session)
    session.open_containers.clear()   # the chests of the old zone
    session.location = location
    session.position = position
    session.state = {}
    storage.mark_dirty(session, "character")
    await session.send({"type": "change_location", "location": location, "position": position})
    await appear(session)
    return True
