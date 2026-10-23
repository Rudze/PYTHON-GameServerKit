"""Items lying on the ground, per zone, with everything inside them (a dropped bag keeps its
contents). A zone's items are read from the database the first time someone needs them, then
kept in memory; every change is written at once."""
from dataclasses import dataclass

from server import storage
from server.modules.inventory.items import ItemInstance, is_known


@dataclass
class WorldItem:
    location: str
    x: float
    y: float
    z: float
    rot: float
    item: ItemInstance

    @property
    def uid(self) -> str:
        return self.item.uid

    async def save(self):
        await storage.save_world_item(self.uid, self.location, self.x, self.y, self.z, self.rot, self.item.to_json())


_zones: dict[str, dict[str, WorldItem]] = {}   # location -> uid -> item on the ground


async def at(location: str) -> dict[str, WorldItem]:
    if location not in _zones:
        items = {}
        for row in await storage.load_world_items(location):
            if not is_known(row["item"]):
                await storage.delete_world_item(row["uid"])
                continue
            item = ItemInstance.from_json(row["item"])
            items[item.uid] = WorldItem(location, row["x"], row["y"], row["z"], row["rot"], item)
        _zones.setdefault(location, items)
    return _zones[location]


async def add(location: str, item: ItemInstance, x: float, y: float, z: float, rot: float = 0.0) -> WorldItem:
    item.rotated = False
    world_item = WorldItem(location, x, y, z, rot, item)
    (await at(location))[item.uid] = world_item
    await world_item.save()
    return world_item


async def remove(location: str, uid: str) -> WorldItem | None:
    world_item = (await at(location)).pop(uid, None)
    if world_item is not None:
        await storage.delete_world_item(uid)
    return world_item


async def root_of(location: str, uid: str) -> WorldItem | None:
    """The item on the ground that is `uid` or holds it."""
    for world_item in (await at(location)).values():
        if any(inner.uid == uid for inner in world_item.item.walk()):
            return world_item
    return None


def view(world_item: WorldItem) -> dict:
    from server.modules.inventory.items import view as item_view
    return {**item_view(world_item.item), "x": world_item.x, "y": world_item.y, "z": world_item.z,
            "rot": world_item.rot}
