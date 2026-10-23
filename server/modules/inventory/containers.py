"""Every place an item can be, behind one interface, so that moving an item works the same from
anywhere to anywhere (pocket -> bag, bag -> chest on the ground, belt -> equipment slot...):

    get(key) -> item or None      remove(key) -> item or None
    check(item, key, rotate) -> "" if allowed, else the reason
    put(item, key, rotate)        (after check)

The containers:
    GridContainer   a Grid: the player's pocket and equipment slots, the inside of a bag / chest
    SlotsContainer  named slots of an item (a belt with "left" and "right"), each one accepting
                    items by tag ("accepts": the item must "provide" one of these tags)

An item definition says what it holds (items.json):
    "container": {"kind": "grid", "rows": 4, "cols": 6, "accepts": []}
    "container": {"kind": "slots", "slots": [{"name": "left", "accepts": ["potion"]}]}
("accepts": [] or missing = any item.)"""
from server.modules.inventory.grid import Grid
from server.modules.inventory.items import ItemInstance

MAX_DEPTH = 16   # a bag in a bag in a bag...: hard limit against malicious clients


def accepted(accepts: list, item: ItemInstance) -> bool:
    return not accepts or bool(set(accepts) & set(item.definition.get("provides", [])))


def contains(item: ItemInstance, uid: str) -> bool:
    """True if `uid` is `item` or anything inside it."""
    return any(inner.uid == uid for inner in item.walk())


def depth(item: ItemInstance) -> int:
    children = item.children()
    return 1 + (max(depth(child) for child in children) if children else 0)


class GridContainer:
    def __init__(self, grid: Grid, holder: ItemInstance | None = None, accepts: list | None = None):
        self.grid = grid
        self.holder = holder         # the bag / chest owning the grid, None for a player's own
        self.accepts = accepts or []
        self.slots = grid.slots

    @staticmethod
    def _index(key) -> int | None:
        try:
            return int(key)
        except (TypeError, ValueError):
            return None

    def get(self, key):
        index = self._index(key)
        return None if index is None else self.grid.slots.get(index)

    def remove(self, key):
        index = self._index(key)
        return None if index is None else self.grid.remove(index)

    def check(self, item: ItemInstance, key, rotate: bool = False) -> str:
        index = self._index(key)
        if index is None:
            return "Invalid slot"
        if self.holder is not None:
            if contains(item, self.holder.uid):
                return "Cannot put an item inside itself"
            if depth(item) >= MAX_DEPTH:
                return "Too many nested containers"
        if not accepted(self.accepts, item):
            return "This item does not go here"
        if not self.grid.can_place(item, index, rotate):
            return "Invalid placement"
        return ""

    def put(self, item: ItemInstance, key, rotate: bool = False):
        self.grid.place(item, int(key), rotate)

    def first_free(self, item: ItemInstance):
        free = self.grid.first_free(item)
        if free is None or self.check(item, free[0], free[1]):
            return None
        return free


class SlotsContainer:
    def __init__(self, holder: ItemInstance, definitions: list[dict]):
        self.holder = holder
        if holder.container is None:
            holder.container = {}
        self.slots: dict[str, ItemInstance] = holder.container.setdefault("slots", {})
        self.definitions = {slot["name"]: slot for slot in definitions}

    def get(self, key):
        return self.slots.get(str(key))

    def remove(self, key):
        return self.slots.pop(str(key), None)

    def check(self, item: ItemInstance, key, rotate: bool = False) -> str:
        slot = self.definitions.get(str(key))
        if slot is None:
            return "Invalid slot"
        if contains(item, self.holder.uid):
            return "Cannot put an item inside itself"
        if depth(item) >= MAX_DEPTH:
            return "Too many nested containers"
        if str(key) in self.slots:
            return "Slot occupied"
        if not accepted(slot.get("accepts", []), item):
            return "This item does not go here"
        return ""

    def put(self, item: ItemInstance, key, rotate: bool = False):
        item.rotated = False
        self.slots[str(key)] = item

    def first_free(self, item: ItemInstance):
        return next(((name, False) for name in self.definitions if not self.check(item, name)), None)


def container_of(item: ItemInstance):
    """The container inside an item, or None if it holds nothing."""
    spec = item.definition.get("container")
    if not spec:
        return None
    if spec.get("kind") == "grid":
        if item.container is None:
            item.container = {}
        grid = Grid(spec.get("rows", 1), spec.get("cols", 1), item.container.setdefault("slots", {}))
        return GridContainer(grid, item, spec.get("accepts"))
    if spec.get("kind") == "slots":
        return SlotsContainer(item, spec.get("slots", []))
    return None


def walk(container):
    """(container, key, item) for every item in `container` and, recursively, inside them."""
    for key, item in list(container.slots.items()):
        yield container, key, item
        inner = container_of(item)
        if inner is not None:
            yield from walk(inner)


def locate(roots, uid: str):
    """Finds an item by uid in some root containers: (container, key, item) or None."""
    for root in roots:
        for found in walk(root):
            if found[2].uid == uid:
                return found
    return None
