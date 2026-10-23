"""Everything the game server reads from and writes to the database.

Saving is grouped and never blocks the game: a change calls

    storage.mark_dirty(session, "character")   # or "inventory"

and the save happens AUTOSAVE_DELAY seconds later, once for all the changes made in between.
`flush(session)` saves at once (disconnection). Positions change all the time: they are saved
every POSITION_SAVE_INTERVAL seconds (and on disconnection), not at every step."""
import asyncio

from common import db
from common.config import settings
from common.log import log
from server.session import Session

POSITION_SAVE_INTERVAL = 30.0
PARTS = ("character", "inventory")

_pending: dict[int, set[str]] = {}          # user id -> parts to save
_tasks: dict[int, asyncio.Task] = {}        # user id -> the waiting save


# ---------------------------------------------------------
# Characters
# ---------------------------------------------------------

async def load_character(user_id: int):
    return await db.pool().fetchrow("SELECT * FROM characters WHERE user_id = $1", user_id)


async def save_character(session: Session):
    await db.pool().execute("""
        INSERT INTO characters (user_id, name, level, exp, health, stamina, appearance, location, position)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (user_id) DO UPDATE SET
            name = EXCLUDED.name, level = EXCLUDED.level, exp = EXCLUDED.exp,
            health = EXCLUDED.health, stamina = EXCLUDED.stamina, appearance = EXCLUDED.appearance,
            location = EXCLUDED.location, position = EXCLUDED.position, updated_at = now()""",
        session.user_id, session.name, session.progression.level, session.progression.exp,
        session.health.value, session.stamina.value, session.appearance, session.location, session.position)
    session.position_dirty = False


# ---------------------------------------------------------
# Inventories (a player's, and later any owner's: a chest, a vehicle...)
# ---------------------------------------------------------

async def load_inventory(owner_type: str, owner_id) -> dict | None:
    return await db.pool().fetchval(
        "SELECT containers FROM inventories WHERE owner_type = $1 AND owner_id = $2", owner_type, str(owner_id))


async def save_inventory(owner_type: str, owner_id, containers: dict):
    await db.pool().execute("""
        INSERT INTO inventories (owner_type, owner_id, containers) VALUES ($1, $2, $3)
        ON CONFLICT (owner_type, owner_id) DO UPDATE SET containers = EXCLUDED.containers, updated_at = now()""",
        owner_type, str(owner_id), containers)


# ---------------------------------------------------------
# Items on the ground
# ---------------------------------------------------------

async def load_world_items(location: str) -> list:
    return await db.pool().fetch("SELECT uid, x, y, z, rot, item FROM world_items WHERE location = $1", location)


async def save_world_item(uid: str, location: str, x: float, y: float, z: float, rot: float, item: dict):
    await db.pool().execute("""
        INSERT INTO world_items (uid, location, x, y, z, rot, item) VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (uid) DO UPDATE SET location = EXCLUDED.location, x = EXCLUDED.x, y = EXCLUDED.y,
            z = EXCLUDED.z, rot = EXCLUDED.rot, item = EXCLUDED.item""",
        uid, location, x, y, z, rot, item)


async def delete_world_item(uid: str):
    await db.pool().execute("DELETE FROM world_items WHERE uid = $1", uid)


# ---------------------------------------------------------
# Grouped saves
# ---------------------------------------------------------

def mark_dirty(session: Session, *parts: str):
    """Asks for `parts` of a player ("character", "inventory") to be saved soon."""
    for part in parts:
        if part not in PARTS:
            raise ValueError(f"Unknown save part: {part}")
    _pending.setdefault(session.user_id, set()).update(parts)
    if session.user_id not in _tasks:
        _tasks[session.user_id] = asyncio.get_running_loop().create_task(_save_later(session))


async def _save_later(session: Session):
    await asyncio.sleep(settings().autosave_delay)
    _tasks.pop(session.user_id, None)
    await _save(session, _pending.pop(session.user_id, set()))


async def _save(session: Session, parts: set[str]):
    from server.modules.inventory import handlers as inventory
    if not parts or session.health is None:
        return   # nothing to save, or the character never finished loading
    async with session.save_lock:
        try:
            if "character" in parts:
                await save_character(session)
            if "inventory" in parts:
                await save_inventory("player", session.user_id, inventory.to_json(session))
        except Exception:
            log.exception("Save failed for %s (%s)", session.username, ", ".join(sorted(parts)))


async def flush(session: Session):
    """Saves everything of a player now (disconnection, server stop)."""
    task = _tasks.pop(session.user_id, None)
    if task is not None:
        task.cancel()
    _pending.pop(session.user_id, None)
    await _save(session, set(PARTS))


async def save_positions_forever(players: dict):
    """Background task: saves the players who moved since their last save."""
    while True:
        await asyncio.sleep(POSITION_SAVE_INTERVAL)
        for session in list(players.values()):
            if session.position_dirty:
                mark_dirty(session, "character")
