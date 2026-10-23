"""A connected player: their account, their character, their inventories, where they are.

Everything a module needs about a player is here; the modules (server/modules/*) read and change
it, then call storage.mark_dirty(session, ...) so it gets saved."""
import asyncio
import json

from server.stats import Gauge, Progression


class Session:
    def __init__(self, user_id: int, username: str, is_admin: bool, websocket):
        self.user_id = user_id
        self.username = username
        self.is_admin = is_admin
        self.websocket = websocket

        # Character (loaded by character.load)
        self.name = username
        self.health: Gauge | None = None
        self.stamina: Gauge | None = None
        self.progression: Progression | None = None
        self.appearance: dict = {}

        # Where they are: a zone ("location") and their last position in it, as the client sends
        # it ({"x", "y", "z", "rot"}; None = the spawn of the zone). See world.py.
        self.location: str | None = None
        self.position: dict | None = None
        self.state: dict = {}            # how the character moves (movement.py)
        self.last_state_time = 0.0
        self.position_dirty = False      # moved since the last save (storage.py saves it now and then)

        # False while out of the world (character creator, menus): the others do not see them
        self.in_world = True

        # Inventories: name ("pocket", an equipment slot) -> Grid (see modules/inventory)
        self.inventories: dict = {}
        self.open_containers: set[str] = set()   # uids of the item containers they look into
        self.last_worn: dict | None = None

        # Flood protection (router.py, chat.py)
        self.message_budget = 0.0
        self.last_message_time = 0.0
        self.last_chat_time = 0.0

        # Set once the player is gone and saved (a new connection of the same account waits for it)
        self.closed = asyncio.Event()
        self.save_lock = asyncio.Lock()   # one save of this player at a time, in order (storage.py)

    async def send(self, message: dict):
        """Sends a message; a closed connection is ignored (its disconnection is handled elsewhere)."""
        try:
            await self.websocket.send(json.dumps(message, separators=(",", ":")))
        except Exception:
            pass

    async def error(self, text: str, code: str = ""):
        await self.send({"type": "error", "code": code, "message": text})

    def public(self) -> dict:
        """What the other players need to show this player."""
        from server.modules.inventory.handlers import worn
        return {"user_id": self.user_id, "name": self.name, "appearance": self.appearance,
                "worn": worn(self), "position": self.position, "state": self.state}

    def __repr__(self):
        return f"Session({self.user_id}, {self.username}, {self.location})"
