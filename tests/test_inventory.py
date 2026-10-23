from server.modules.inventory.containers import GridContainer, SlotsContainer, container_of, locate
from server.modules.inventory.grid import Grid
from server.modules.inventory.items import ItemInstance


def test_place_and_overlap():
    grid = Grid(4, 8)
    sword = ItemInstance("iron_sword")        # 1 x 3
    assert grid.can_place(sword, 0)
    grid.place(sword, 0)
    assert not grid.can_place(ItemInstance("stone"), 8)    # row 1, col 0: under the sword
    assert grid.can_place(ItemInstance("stone"), 1)


def test_out_of_grid():
    grid = Grid(2, 8)
    assert not grid.can_place(ItemInstance("iron_sword"), 0)          # 3 high in a 2 rows grid
    assert grid.can_place(ItemInstance("iron_sword"), 0, rotate=True)  # 3 wide once rotated
    assert not grid.can_place(ItemInstance("wood_log"), 7)            # 2 wide on the last column


def test_add_stacks_then_new_places():
    grid = Grid(1, 2)
    assert grid.add(ItemInstance("stone", {"quantity": 30})) == 0
    assert grid.add(ItemInstance("stone", {"quantity": 30})) == 0      # 20 on the first stack, 10 new
    quantities = sorted(item.quantity for item in grid.slots.values())
    assert quantities == [10, 50]
    assert grid.add(ItemInstance("stone", {"quantity": 100})) == 60    # 40 more fit


def test_add_rotates_when_needed():
    grid = Grid(1, 3)
    sword = ItemInstance("iron_sword")
    assert grid.add(sword) == 0
    assert sword.rotated and sword.size() == (3, 1)


def test_move_in_same_grid_ignores_itself():
    grid = Grid(4, 8)
    grid.place(ItemInstance("wooden_shield"), 0)                     # 2 x 2
    container = GridContainer(grid)
    shield = container.get(0)
    assert container.check(shield, 1) == ""                          # overlaps only its old cells


def test_equipment_slot():
    head = Grid(1, 1, equip_slot="head")
    assert head.can_place(ItemInstance("leather_cap"), 0)            # 2 x 2 in a 1 x 1 slot: fine
    assert not head.can_place(ItemInstance("leather_boots"), 0)
    head.place(ItemInstance("leather_cap"), 0)
    assert not head.can_place(ItemInstance("leather_cap"), 0)        # occupied


def test_bag_cannot_go_inside_itself():
    bag = ItemInstance("small_backpack")
    inner = container_of(bag)
    assert inner.check(bag, 0) == "Cannot put an item inside itself"
    other = ItemInstance("small_backpack")
    inner.put(other, 0)
    assert container_of(other).check(bag, 0) == "Cannot put an item inside itself"


def test_slots_accept_tags():
    belt = ItemInstance("potion_belt")
    slots = container_of(belt)
    assert isinstance(slots, SlotsContainer)
    assert slots.check(ItemInstance("stone"), "left") == "This item does not go here"
    assert slots.check(ItemInstance("health_potion"), "left") == ""
    assert slots.check(ItemInstance("health_potion"), "middle") == "Invalid slot"


def test_save_and_load_keeps_nesting():
    bag = ItemInstance("small_backpack")
    container_of(bag).put(ItemInstance("stone", {"quantity": 7}), 3)
    loaded = ItemInstance.from_json(bag.to_json())
    assert loaded.uid == bag.uid
    stone = container_of(loaded).get(3)
    assert stone.item_id == "stone" and stone.quantity == 7


def test_unknown_items_are_dropped_when_loading():
    bag = ItemInstance("small_backpack")
    raw = bag.to_json()
    raw["container"] = {"slots": {"0": {"uid": "x", "item_id": "removed_item", "data": {}}}}
    assert ItemInstance.from_json(raw).children() == []


def test_locate_finds_nested_items():
    pocket = Grid(4, 8)
    bag = ItemInstance("small_backpack")
    stone = ItemInstance("stone")
    container_of(bag).put(stone, 0)
    pocket.place(bag, 0)
    container, key, item = locate([GridContainer(pocket)], stone.uid)
    assert item is stone and key == 0 and container.holder is bag
