"""The character of a player: name, health, stamina, level, exp, look.

Any change, wherever it comes from (combat, food, a quest...),
    session.health.remove(10)
    session.progression.add_exp(50)
is saved and sent to the player ({"type": "stats"}) on its own.

Character creator: the client sends "leave_world" (the others stop seeing the player), then
"set_name" / "set_appearance", then "spawn" (they appear again, with their new look)."""
import asyncio
import math
import re

from server import content, storage, world
from server.router import handler
from server.session import Session
from server.stats import Gauge, Progression

NAME_RULE = re.compile(r"^[^\W_][\w '-]{1,14}[^\W_]$")   # 3 to 16 letters (any alphabet), digits, space ' -
PART_ID = re.compile(r"^[a-z0-9_]{1,64}$")


def load(session: Session, row):
    """Fills the session from its saved character (row None: a new player, with the defaults)."""
    rules = content.RULES
    session.health = Gauge(rules.health, row["health"] if row else None)
    session.stamina = Gauge(rules.stamina, row["stamina"] if row else None)
    session.progression = Progression(row["level"] if row else 1, row["exp"] if row else 0,
                                      rules.max_level, rules.exp_per_level)
    if row:
        session.name = row["name"]
        session.appearance = row["appearance"] or {}
        session.location = row["location"]
        session.position = row["position"]
    if not world.is_location(session.location):
        session.location, session.position = rules.default_location, None
    for part in (session.health, session.stamina, session.progression):
        part.on_change = lambda _part: changed(session)


def stats(session: Session) -> dict:
    return {"name": session.name, "health": session.health.to_dict(), "stamina": session.stamina.to_dict(),
            "progression": session.progression.to_dict()}


async def send_stats(session: Session):
    await session.send({"type": "stats", **stats(session)})


def changed(session: Session):
    """Something of the character changed: save it soon, tell the player."""
    storage.mark_dirty(session, "character")
    asyncio.get_running_loop().create_task(send_stats(session))


def clean_name(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    name = " ".join(raw.split())
    return name if NAME_RULE.match(name) else None


# ---------------------------------------------------------
# Messages
# ---------------------------------------------------------

@handler("request_stats", out_of_world=True)
async def on_request_stats(session: Session, data: dict):
    await send_stats(session)


@handler("leave_world")
async def on_leave_world(session: Session, data: dict):
    """The character creator (or a full screen menu) opens: the others stop seeing the player."""
    await world.disappear(session)
    session.in_world = False


@handler("spawn", out_of_world=True)
async def on_spawn(session: Session, data: dict):
    """Back in the world, where they left, with their look."""
    if session.in_world:
        return
    session.in_world = True
    await world.appear(session)


@handler("set_name", out_of_world=True)
async def on_set_name(session: Session, data: dict):
    """{"name"}: only out of the world (character creator)."""
    if session.in_world:
        await session.error("Open the character creator first", "not_in_creator")
        return
    name = clean_name(data.get("name"))
    if name is None:
        await session.error("Name: 3 to 16 letters, digits, spaces, ' or -", "invalid_name")
        return
    session.name = name
    changed(session)


@handler("set_appearance", out_of_world=True)
async def on_set_appearance(session: Session, data: dict):
    """{"parts": {"hair": "short_01", "beard": "", "height": 0.4}}: only the given entries change.
    A part (game.json "appearance.parts") is an id ("" = none); a number ("appearance.numbers")
    must be within its [min, max]. Only out of the world (character creator)."""
    if session.in_world:
        await session.error("Open the character creator first", "not_in_creator")
        return
    parts = data.get("parts")
    if not isinstance(parts, dict) or not parts:
        await session.error("Missing parts", "invalid_appearance")
        return
    rules = content.RULES
    for key, value in parts.items():
        if key in rules.appearance_numbers:
            low, high = rules.appearance_numbers[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                    or not low <= value <= high:
                await session.error(f"Invalid value for {key}", "invalid_appearance")
                return
        elif key not in rules.appearance_parts or not isinstance(value, str) or (value and not PART_ID.match(value)):
            await session.error(f"Invalid appearance part: {key}", "invalid_appearance")
            return
    session.appearance.update(parts)
    storage.mark_dirty(session, "character")
    await session.send({"type": "appearance", "appearance": session.appearance})
