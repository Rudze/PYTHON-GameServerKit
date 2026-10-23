# Extending the kit

The kit gives the base; your gameplay (combat, harvesting, crafting, quests, trading...) is added as **modules**, without changing the core.

## Adding a module

Example: an "eat" message that consumes an item of the pocket and heals.

**1.** Create `server/modules/food.py`:

```python
"""Eating: {"type": "eat", "key": <pocket index>} consumes one food item and heals."""
from server.modules.inventory import handlers as inventory
from server.router import handler
from server.session import Session


@handler("eat")
async def on_eat(session: Session, data: dict):
    pocket = session.inventories["pocket"]
    item = pocket.slots.get(data.get("key"))
    heal = item.definition.get("heal", 0) if item else 0   # a free field of items.json
    if heal <= 0:
        await session.error("You cannot eat this", "not_food")
        return
    item.quantity -= 1
    if item.quantity <= 0:
        pocket.remove(data["key"])
    session.health.add(heal)                 # saved and sent ("stats") on its own
    await inventory.after_change(session)    # inventory saved and sent
```

**2.** Import it in `server/modules/__init__.py`:

```python
from server.modules import character, chat, food, movement   # noqa: F401
```

**3.** In `items.json`: `{"id": "apple", "name": "Apple", "stackable": true, "max_stack": 20, "heal": 15}`.

That's all: the client sends `{"type": "eat", "key": 0}`.

## What the core gives you

| Tool | Role |
|---|---|
| `@handler("type")` | Declares the function of a message. `@handler("type", out_of_world=True)`: also accepted in the character creator |
| `session.send(message)` | Sends a message to the player |
| `session.error(text, code)` | Sends an error |
| `world.broadcast(session, message, include_self=False)` | To every player of their zone |
| `world.broadcast_all(message)` | To the whole server |
| `world.players`, `world.at(zone)`, `world.find(name)` | The connected players |
| `world.send_to(session, zone, position=None)` | Moves a player to a zone (portals, teleport) |
| `world.on_join`, `world.on_leave` | Lists of `async f(session)` functions called when a player arrives and leaves |
| `world.tasks` | List of `async f()` functions run in the background while the server runs |
| `session.health`, `session.stamina` | `Gauge`s: `add(n)`, `remove(n)`, `value`, `maximum`, `is_empty` |
| `session.progression` | `add_exp(n)` (returns the levels gained), `level`, `exp` |
| `await inventory.give(session, "stone", 12)` | Gives items; returns what did not fit |
| `await inventory.after_change(session)` | After changing the inventory by hand: save and send |
| `await world_items.add(zone, ItemInstance("stone"), x, y, z)` | Puts an item on the ground (loot, harvest) |
| `storage.mark_dirty(session, "character")` | Save soon (grouped) |
| `content.RULES`, `content.ITEMS` | The rules of `game.json`, the items of `items.json` (all their fields) |
| `session.is_admin` | For restricted commands |
| `from common.log import log` | `log.info(...)`, `log.warning(...)` |

## Reacting to a player arriving

```python
# server/modules/welcome_message.py
from server import world


async def greet(session):
    await session.send({"type": "chat", "channel": "global", "user_id": 0, "name": "Server",
                        "message": f"Welcome {session.name}!"})

world.on_join.append(greet)
```

## A background task (respawn, weather, day / night cycle)

```python
# server/modules/day_night.py
import asyncio

from server import world

DAY_LENGTH = 1200   # seconds


async def run():
    hour = 0
    while True:
        await asyncio.sleep(DAY_LENGTH / 24)
        hour = (hour + 1) % 24
        await world.broadcast_all({"type": "time_of_day", "hour": hour})

world.tasks.append(run)   # started with the server, stopped with it
```

## Saving your own data

**A new column** (simple, for one value per character): a migration `migrations/002_gold.sql`, then read and write it in `server/storage.py` (`load_character` already reads the whole row; add the column to `save_character`).

**A new table** (for separate data: quests, guilds, base chests): a migration, then `async` functions in your module using `db.pool()`:

```python
from common import db

async def load_quests(user_id: int) -> list:
    return await db.pool().fetch("SELECT quest_id, step FROM quests WHERE user_id = $1", user_id)
```

**An inventory that is not a player's** (a base chest, a bank): `storage.load_inventory("chest", uid)` and `storage.save_inventory("chest", uid, containers)` are already generic.

## Movement anti-cheat

The server relays movement without checking it. For a competitive game, add a speed check in `on_state` (`server/modules/movement.py`), right after `state = read_state(data)`:

```python
MAX_SPEED = 12.0   # meters per second, with some margin

elapsed = now - session.last_state_time
if session.position and elapsed < 1.0:
    distance = math.dist((state["x"], state["z"]), (session.position["x"], session.position["z"]))
    if distance > MAX_SPEED * elapsed:
        return   # ignored: the others still see the last valid position
```

To also put the player back on their own screen, send them a message of yours (for example `{"type": "correct_position", "position": session.position}`) that your client applies.

## Tests

`pytest` runs `tests/`. The logic (grids, containers, stats) is tested without a database: see `tests/test_inventory.py`. `scripts/smoke_test.py` tests the whole path with real clients, on a test database.
