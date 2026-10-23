"""A grid of cells holding items (Tarkov / Resident Evil style): the pocket, the inside of a
bag or a chest. An item takes width x height cells from its top-left cell (its "index",
index = row * cols + col), and can be rotated.

An equipment slot is a 1 x 1 grid that accepts one item whose "equip_slot" is the slot name
(whatever the item's size)."""
from server.modules.inventory.items import ItemInstance


class Grid:
    def __init__(self, rows: int, cols: int, slots: dict | None = None, equip_slot: str = ""):
        self.rows = rows
        self.cols = cols
        self.slots: dict[int, ItemInstance] = {} if slots is None else slots   # index -> item
        self.equip_slot = equip_slot     # "" for a normal grid

    # -------------------------------------------------------
    # Questions
    # -------------------------------------------------------

    def cells(self, index: int, width: int, height: int) -> list[int] | None:
        """The cells an item of width x height takes at `index`, None if it goes out of the grid."""
        if not 0 <= index < self.rows * self.cols:
            return None
        row, col = divmod(index, self.cols)
        if col + width > self.cols or row + height > self.rows:
            return None
        return [r * self.cols + c for r in range(row, row + height) for c in range(col, col + width)]

    def is_free(self, cells: list[int], ignore: ItemInstance | None = None) -> bool:
        wanted = set(cells)
        for index, item in self.slots.items():
            if item is ignore:
                continue
            taken = self.cells(index, *item.size()) or [index]
            if wanted.intersection(taken):
                return False
        return True

    def can_place(self, item: ItemInstance, index: int, rotate: bool = False) -> bool:
        """Can `item` (from anywhere) go at `index`, rotated a quarter turn more if `rotate`?"""
        if self.equip_slot:
            return index == 0 and not self.slots and item.definition.get("equip_slot") == self.equip_slot
        width, height = item.size()
        if rotate:
            width, height = height, width
        cells = self.cells(index, width, height)
        return cells is not None and self.is_free(cells, ignore=item)

    def first_free(self, item: ItemInstance) -> tuple[int, bool] | None:
        """The first place where `item` fits: (index, rotate), or None."""
        for index in range(self.rows * self.cols):
            for rotate in (False, True):
                if self.can_place(item, index, rotate):
                    return index, rotate
        return None

    # -------------------------------------------------------
    # Changes
    # -------------------------------------------------------

    def place(self, item: ItemInstance, index: int, rotate: bool = False):
        """Puts `item` at `index`. Call can_place() first."""
        if self.equip_slot:
            item.rotated = False
        elif rotate:
            item.rotated = not item.rotated
        self.slots[index] = item

    def remove(self, index: int) -> ItemInstance | None:
        return self.slots.pop(index, None)

    def add(self, item: ItemInstance) -> int:
        """Puts an item anywhere it fits: first on the existing stacks of the same item, then in
        free places. Returns the quantity left over (0: all of it went in). A stack placed in
        several parts makes new instances; a single item keeps its own (and its uid)."""
        definition = item.definition
        if not item.stackable:
            free = self.first_free(item)
            if free is None:
                return 1
            self.place(item, *free)
            return 0

        max_stack = definition.get("max_stack", 1)
        remaining = item.quantity
        for existing in self.slots.values():
            if existing.item_id == item.item_id and existing.quantity < max_stack:
                moved = min(max_stack - existing.quantity, remaining)
                existing.quantity += moved
                remaining -= moved
                if remaining == 0:
                    return 0
        while remaining > 0:
            part = ItemInstance(item.item_id, {**item.data, "quantity": min(remaining, max_stack)})
            part.rotated = False
            free = self.first_free(part)
            if free is None:
                break
            self.place(part, *free)
            remaining -= part.quantity
        return remaining

    # -------------------------------------------------------
    # Saving
    # -------------------------------------------------------

    def to_json(self) -> dict:
        return {str(index): item.to_json() for index, item in self.slots.items()}
