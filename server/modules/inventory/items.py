"""Item instances: one real item (this sword, these 12 stones), made from a definition of
items.json (content.ITEMS).

    ItemInstance("stone", {"quantity": 12})

An instance has its own uid, free `data` (quantity, rotated, durability, anything a game adds)
and, for an item that holds others (a bag, a chest, a belt), `container` = {"slots": {key: child}}.
Saved as JSON: {"uid", "item_id", "data", "container"?}."""
import uuid

from common.log import log
from server import content


def new_uid() -> str:
    return uuid.uuid4().hex


class ItemInstance:
    def __init__(self, item_id: str, data: dict | None = None, uid: str | None = None,
                 container: dict | None = None):
        self.uid = uid or new_uid()
        self.item_id = item_id
        self.data = data or {}
        self.container = container

    @property
    def definition(self) -> dict:
        return content.ITEMS.get(self.item_id) or {}

    @property
    def quantity(self) -> int:
        return self.data.get("quantity", 1)

    @quantity.setter
    def quantity(self, value: int):
        self.data["quantity"] = value

    @property
    def rotated(self) -> bool:
        return self.data.get("rotated", False)

    @rotated.setter
    def rotated(self, value: bool):
        if value:
            self.data["rotated"] = True
        else:
            self.data.pop("rotated", None)

    @property
    def stackable(self) -> bool:
        return bool(self.definition.get("stackable"))

    def size(self) -> tuple[int, int]:
        """(width, height) taken in a grid, rotation included."""
        width, height = self.definition.get("width", 1), self.definition.get("height", 1)
        return (height, width) if self.rotated else (width, height)

    def children(self) -> list["ItemInstance"]:
        return list((self.container or {}).get("slots", {}).values())

    def walk(self):
        """This item, then everything inside it, recursively."""
        yield self
        for child in self.children():
            yield from child.walk()

    def to_json(self) -> dict:
        result = {"uid": self.uid, "item_id": self.item_id, "data": self.data}
        if self.container is not None:
            result["container"] = {**self.container, "slots": {str(key): child.to_json()
                                                               for key, child in self.container.get("slots", {}).items()}}
        return result

    @classmethod
    def from_json(cls, raw: dict) -> "ItemInstance":
        container = raw.get("container")
        instance = cls(raw["item_id"], dict(raw.get("data", {})), raw.get("uid"))
        if container is not None:
            grid = (instance.definition.get("container") or {}).get("kind") == "grid"
            slots = {}
            for key, child in container.get("slots", {}).items():
                if is_known(child):
                    slots[int(key) if grid else str(key)] = cls.from_json(child)
            instance.container = {**container, "slots": slots}
        return instance

    def __repr__(self):
        return f"Item({self.item_id}, {self.uid[:8]})"


def is_known(raw: dict) -> bool:
    """False for a saved item whose definition was removed from items.json: it is dropped."""
    if raw.get("item_id") in content.ITEMS:
        return True
    log.warning("Item '%s' no longer exists in items.json: removed", raw.get("item_id"))
    return False


def view(item: ItemInstance) -> dict:
    """What a client gets for an item. It has items.json too (same content hash), so the name,
    icon, description... come from there; only what is specific to this instance is sent."""
    width, height = item.size()
    kind = (item.definition.get("container") or {}).get("kind")
    return {"uid": item.uid, "item_id": item.item_id, "quantity": item.quantity, "rotated": item.rotated,
            "width": width, "height": height, "container_kind": kind, "data": item.data}
