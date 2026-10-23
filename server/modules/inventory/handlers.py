"""The inventory of a player, and the messages to use it.

A player has a "pocket" (a grid, size in game.json) and one equipment slot per name of
game.json "equipment_slots". Items holding others (bags, chests, belts) are opened by uid.

An address names a container in messages:
    "pocket", "head", "back"...   the player's own (pocket or equipment slot)
    "<item uid>"                  the inside of an item the player carries, or of an item on the
                                  ground near them (a chest, a dropped bag)

For game code (loot, crafting, quests...):
    leftover = await inventory.give(session, "stone", 12)   # 0: everything fitted
    ...change session.inventories by hand...; await inventory.after_change(session)"""
import math

from common.log import log
from server import content, storage, world
from server.router import handler
from server.session import Session
from server.modules.inventory import world_items
from server.modules.inventory.containers import GridContainer, accepted, contains, container_of, locate
from server.modules.inventory.grid import Grid
from server.modules.inventory.items import ItemInstance, is_known, view


# ---------------------------------------------------------
# Loading, saving, what the others see
# ---------------------------------------------------------

def load(session: Session, saved: dict | None):
    """Builds the player's inventories from the saved JSON (None: a new player).
    An item that no longer fits (the pocket got smaller in game.json...) is put elsewhere."""
    rows, cols = content.RULES.pocket
    session.inventories = {"pocket": Grid(rows, cols)}
    for slot in content.RULES.equipment_slots:
        session.inventories[slot] = Grid(1, 1, equip_slot=slot)
    misplaced = []
    for name, container in (saved or {}).items():
        grid = session.inventories.get(name)
        for key, raw in container.get("slots", {}).items():
            if not is_known(raw):
                continue
            item = ItemInstance.from_json(raw)
            if grid is not None and grid.can_place(item, int(key)):
                grid.place(item, int(key))
            else:
                misplaced.append(item)
    for item in misplaced:
        if store(session, item):
            log.warning("No room for %s of %s: removed", item, session.username)


def to_json(session: Session) -> dict:
    return {name: {"slots": grid.to_json()} for name, grid in session.inventories.items() if grid.slots}


def worn(session: Session) -> dict:
    """What the others see the player wear: {"head": "iron_helmet", ...}."""
    return {name: next(iter(grid.slots.values())).item_id
            for name, grid in session.inventories.items() if grid.equip_slot and grid.slots}


async def send_inventory(session: Session):
    containers = {}
    for name, grid in session.inventories.items():
        containers[name] = {"rows": grid.rows, "cols": grid.cols, "equip_slot": grid.equip_slot,
                            "items": {str(key): view(item) for key, item in grid.slots.items()}}
    await session.send({"type": "inventory", "containers": containers})


async def send_look(session: Session):
    """The worn items changed: the others see the new helmet, bag..."""
    now = worn(session)
    if now != session.last_worn:
        session.last_worn = now
        await world.broadcast(session, {"type": "player_look", "user_id": session.user_id,
                                        "appearance": session.appearance, "worn": now})


# ---------------------------------------------------------
# Finding containers and items
# ---------------------------------------------------------

def _own(session: Session) -> list[GridContainer]:
    return [GridContainer(grid) for grid in session.inventories.values()]


def _near(session: Session, x: float, y: float, z: float) -> bool:
    reach = content.RULES.pickup_range
    if reach <= 0 or not session.position:
        return True
    position = session.position
    return math.dist((x, y, z), (position.get("x", 0), position.get("y", 0), position.get("z", 0))) <= reach


async def _find(session: Session, uid: str):
    """An item the player carries, or on the ground within reach: (container, key, item, owner),
    owner = ("player", session) or ("world", world_item). None if not found."""
    found = locate(_own(session), uid)
    if found:
        return (*found, ("player", session))
    world_item = await world_items.root_of(session.location, uid)
    if world_item is None or not _near(session, world_item.x, world_item.y, world_item.z):
        return None
    if world_item.uid == uid:
        return None, uid, world_item.item, ("world", world_item)
    found = locate([container_of(world_item.item)], uid)
    return (*found, ("world", world_item)) if found else None


async def _resolve(session: Session, address):
    """The container at an address and its owner, or (None, None)."""
    if address in session.inventories:
        return GridContainer(session.inventories[address]), ("player", session)
    found = await _find(session, str(address)) if isinstance(address, str) and address else None
    if found is None:
        return None, None
    container = container_of(found[2])
    return (container, found[3]) if container is not None else (None, None)


def carry_targets(session: Session) -> list:
    """Where picked up / given items go, in the order of game.json "carry": the pocket, then the
    inside of what is worn in the listed equipment slots (a backpack...)."""
    targets = []
    for name in content.RULES.carry:
        grid = session.inventories.get(name)
        if grid is None:
            continue
        if name == "pocket":
            targets.append(GridContainer(grid))
        elif grid.slots:
            inner = container_of(next(iter(grid.slots.values())))
            if inner is not None:
                targets.append(inner)
    return targets


def _move_into(item: ItemInstance, target) -> bool:
    """Puts `item` (already taken out of its place) in the first room of `target`. A stack may
    go in partly: its quantity is lowered. True if all of it went in."""
    if item.stackable and isinstance(target, GridContainer):
        if not accepted(target.accepts, item):
            return False
        part = ItemInstance(item.item_id, dict(item.data))
        item.quantity = target.grid.add(part)
        return item.quantity == 0
    free = target.first_free(item)
    if free is None:
        return False
    target.put(item, *free)
    return True


def store(session: Session, item: ItemInstance) -> int:
    """Puts an item in what the player carries (carry_targets). Returns the quantity that did
    not fit (0: all of it). Does not save nor send: give() does."""
    for target in carry_targets(session):
        if _move_into(item, target):
            return 0
    return item.quantity if item.stackable else 1


async def give(session: Session, item_id: str, quantity: int = 1, data: dict | None = None) -> int:
    """Gives items to a player (loot, crafting, a quest reward...). Returns what did not fit."""
    if item_id not in content.ITEMS or quantity < 1:
        raise ValueError(f"Cannot give {quantity} x '{item_id}'")
    if content.ITEMS[item_id]["stackable"]:
        leftover = store(session, ItemInstance(item_id, {**(data or {}), "quantity": quantity}))
    else:
        leftover = sum(store(session, ItemInstance(item_id, dict(data or {}))) for _ in range(quantity))
    if leftover < quantity:
        await after_change(session, [("player", session)])
    return leftover


# ---------------------------------------------------------
# After a change: save, then update whoever sees it
# ---------------------------------------------------------

async def after_change(session: Session, owners=None):
    """After an inventory change: saves, then updates the player, the owners, and whoever has an
    affected container open. `owners` = [("player", session) | ("world", world_item)]; None: the
    player's own inventory only."""
    players = {session.user_id: session}
    owners = owners or [("player", session)]
    for kind, owner in owners:
        if kind == "player":
            players[owner.user_id] = owner
        else:
            await owner.save()
    for player in players.values():
        storage.mark_dirty(player, "inventory")
        await send_inventory(player)
        await send_look(player)
    viewers = {player.user_id: player for player in world.at(session.location)}
    viewers[session.user_id] = session
    for player in viewers.values():
        for uid in list(player.open_containers):
            await send_container(player, uid)


# ---------------------------------------------------------
# Item containers (bags, chests, belts)
# ---------------------------------------------------------

async def send_container(session: Session, uid: str):
    found = await _find(session, uid)
    inner = container_of(found[2]) if found else None
    if inner is None:
        session.open_containers.discard(uid)
        await session.send({"type": "container_closed", "uid": uid})
        return
    message = {"type": "container", "uid": uid, "item_id": found[2].item_id,
               "items": {str(key): view(item) for key, item in inner.slots.items()}}
    if isinstance(inner, GridContainer):
        message.update(kind="grid", rows=inner.grid.rows, cols=inner.grid.cols)
    else:
        message.update(kind="slots", slots=list(inner.definitions.values()))
    await session.send(message)


@handler("request_inventory")
async def on_request_inventory(session: Session, data: dict):
    await send_inventory(session)


@handler("open_container")
async def on_open_container(session: Session, data: dict):
    """{"uid"}: looks inside an item carried or on the ground nearby."""
    uid = data.get("uid")
    found = await _find(session, uid) if isinstance(uid, str) else None
    if found is None or container_of(found[2]) is None:
        await session.send({"type": "container_closed", "uid": uid})
        return
    session.open_containers.add(uid)
    await send_container(session, uid)


@handler("close_container")
async def on_close_container(session: Session, data: dict):
    session.open_containers.discard(data.get("uid"))


# ---------------------------------------------------------
# Moving items
# ---------------------------------------------------------

@handler("move_item")
async def on_move_item(session: Session, data: dict):
    """{"from_container", "from", "to_container", "to", "rotate"?, "split"?}: from any container
    to any container. On a stack of the same item, merges; "split" moves half a stack."""
    from_key, to_key = data.get("from"), data.get("to")
    rotate, split = data.get("rotate") is True, data.get("split") is True
    source, source_owner = await _resolve(session, data.get("from_container"))
    target, target_owner = await _resolve(session, data.get("to_container"))
    item = source.get(from_key) if source else None
    if item is None or target is None:
        await session.error("Item or container not found", "not_found")
        return
    owners = [source_owner, target_owner]

    if split and item.stackable and item.quantity > 1:
        part = ItemInstance(item.item_id, {**item.data, "quantity": item.quantity // 2})
        part.rotated = False
        error = target.check(part, to_key, rotate)
        if error:
            await session.error(error, "invalid_move")
            return
        item.quantity -= part.quantity
        target.put(part, to_key, rotate)
        await after_change(session, owners)
        return

    existing = target.get(to_key)
    if existing is not None and existing is not item and item.stackable and existing.item_id == item.item_id:
        moved = min(item.definition["max_stack"] - existing.quantity, item.quantity)
        if moved <= 0:
            await session.error("Stack is full", "stack_full")
            return
        existing.quantity += moved
        item.quantity -= moved
        if item.quantity == 0:
            source.remove(from_key)
        await after_change(session, owners)
        return

    if source.slots is target.slots and str(from_key) == str(to_key) and not rotate:
        return
    error = target.check(item, to_key, rotate)
    if error:
        await session.error(error, "invalid_move")
        return
    source.remove(from_key)
    target.put(item, to_key, rotate)
    await after_change(session, owners)


@handler("quick_move")
async def on_quick_move(session: Session, data: dict):
    """{"container", "key"} (Ctrl + click): from the player's own containers to the open
    containers, or from anywhere else back into what the player carries."""
    address, key = data.get("container"), data.get("key")
    source, source_owner = await _resolve(session, address)
    item = source.get(key) if source else None
    if item is None:
        await session.error("Item not found", "not_found")
        return
    if address in session.inventories:
        targets = []
        for uid in session.open_containers:
            target, owner = await _resolve(session, uid)
            if target is not None and not contains(item, uid):
                targets.append((target, owner))
    else:
        targets = [(target, ("player", session)) for target in carry_targets(session)]

    for target, target_owner in targets:
        if target.slots is source.slots:
            continue
        source.remove(key)
        if _move_into(item, target):
            await after_change(session, [source_owner, target_owner])
            return
        source.put(item, key)   # back where it was (a stack may have partly moved)
        if item.stackable:
            await after_change(session, [source_owner, target_owner])
            return
    await session.error("No room for this item", "no_room")


# ---------------------------------------------------------
# Items on the ground
# ---------------------------------------------------------

def _coordinates(data: dict) -> tuple | None:
    values = [data.get(key, 0) for key in ("x", "y", "z", "rot")]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        return None
    return tuple(float(v) for v in values)


@handler("request_world_items")
async def on_request_world_items(session: Session, data: dict):
    items = await world_items.at(session.location)
    await session.send({"type": "world_items", "location": session.location,
                        "items": [world_items.view(w) for w in items.values()]})


@handler("drop_item")
async def on_drop_item(session: Session, data: dict):
    """{"from_container", "from", "x", "y", "z", "rot"}: puts an item on the ground near the player."""
    source, owner = await _resolve(session, data.get("from_container"))
    item = source.get(data.get("from")) if source else None
    where = _coordinates(data)
    if item is None or owner[0] != "player" or where is None:
        await session.error("Item not found", "not_found")
        return
    if not _near(session, *where[:3]):
        await session.error("Too far", "too_far")
        return
    source.remove(data.get("from"))
    world_item = await world_items.add(session.location, item, *where)
    await world.broadcast(session, {"type": "world_item_added", "item": world_items.view(world_item)},
                          include_self=True)
    await after_change(session, [owner])


@handler("pick_up")
async def on_pick_up(session: Session, data: dict):
    """{"uid", "equip"?}: picks an item up from the ground, into what the player carries
    (or, with "equip": true, straight into its equipment slot)."""
    items = await world_items.at(session.location)
    world_item = items.get(data.get("uid"))
    if world_item is None or not _near(session, world_item.x, world_item.y, world_item.z):
        await session.error("Item not found", "not_found")
        return
    item = world_item.item

    if data.get("equip") is True:
        grid = session.inventories.get(item.definition.get("equip_slot", ""))
        if grid is None or not grid.equip_slot or not grid.can_place(item, 0):
            await session.error("Cannot equip this item", "cannot_equip")
            return
        grid.place(item, 0)
    else:
        whole = item.quantity
        leftover = store(session, item)
        if leftover and (not item.stackable or leftover == whole):
            await session.error("Inventory full", "no_room")
            return
        if leftover:   # part of a stack: the rest stays on the ground
            item.quantity = leftover
            await world_item.save()
            await world.broadcast(session, {"type": "world_item_updated", "item": world_items.view(world_item)},
                                  include_self=True)
            await session.error("Inventory full", "no_room")
            await after_change(session, [("player", session)])
            return

    await world_items.remove(session.location, world_item.uid)
    await world.broadcast(session, {"type": "world_item_removed", "uid": world_item.uid}, include_self=True)
    await after_change(session, [("player", session)])
