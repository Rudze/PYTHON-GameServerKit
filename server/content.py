"""The game data the server follows, in DATA_DIR (data/ by default):
    game.json   the rules: zones, character stats, appearance, inventory, movement, chat
    items.json  the item definitions (see doc/*/game-data.md)
Changing a game means changing these files, not the code.

`content_hash` identifies them: the client gets it in "welcome" (and may send its own when it
connects: with REQUIRE_CONTENT_HASH=true, a client whose data differs is refused)."""
import hashlib
import json
from dataclasses import dataclass, field

from common.config import settings
from common.log import log


@dataclass
class Rules:
    default_location: str = "world"
    locations: list[str] = field(default_factory=list)            # [] = any id (letters, digits, _ : -)
    client_travel: bool = True                                     # may a client ask to go to another zone?
    health: int = 100
    stamina: int = 100
    max_level: int = 100
    exp_per_level: int = 100                                       # exp to the next level = exp_per_level * level
    appearance_parts: list[str] = field(default_factory=list)      # slots holding a part id ("hair": "short_01")
    appearance_numbers: dict[str, list[float]] = field(default_factory=dict)   # number -> [min, max]
    pocket: tuple[int, int] = (2, 8)                               # rows, columns
    equipment_slots: list[str] = field(default_factory=list)       # one item each, matching its "equip_slot"
    carry: list[str] = field(default_factory=lambda: ["pocket"])  # where picked up items go, in order
    pickup_range: float = 4.0                                      # meters to reach a ground item (0 = anywhere)
    state_numbers: dict[str, float] = field(default_factory=dict)  # movement field -> max absolute value
    state_flags: list[str] = field(default_factory=list)           # movement booleans
    state_texts: dict[str, int] = field(default_factory=dict)      # movement short texts -> max length
    states_per_second: float = 20.0
    chat_max_length: int = 200
    chat_per_second: float = 2.0                                   # messages per second a player may send


RULES = Rules()
ITEMS: dict[str, dict] = {}        # item id -> definition (raw from items.json, defaults filled)
content_hash = ""


def _item(entry: dict) -> dict:
    item = {"width": 1, "height": 1, "stackable": False, "max_stack": 1, "equip_slot": "",
            "provides": [], "container": None, **entry}
    if not item["stackable"]:
        item["max_stack"] = 1
    return item


def load():
    """Reads game.json and items.json. Called at start; a broken file stops the server."""
    global RULES, content_hash
    data_dir = settings().data_dir
    raw_game = (data_dir / "game.json").read_bytes()
    raw_items = (data_dir / "items.json").read_bytes()
    game = json.loads(raw_game)
    character = game.get("character", {})
    appearance = game.get("appearance", {})
    inventory = game.get("inventory", {})
    movement = game.get("movement", {})
    zones = game.get("zones", {})
    chat = game.get("chat", {})
    RULES = Rules(
        default_location=zones.get("default", "world"),
        locations=zones.get("list", []),
        client_travel=zones.get("client_travel", True),
        health=character.get("health", 100),
        stamina=character.get("stamina", 100),
        max_level=character.get("max_level", 100),
        exp_per_level=character.get("exp_per_level", 100),
        appearance_parts=appearance.get("parts", []),
        appearance_numbers=appearance.get("numbers", {}),
        pocket=tuple(inventory.get("pocket", [2, 8])),
        equipment_slots=inventory.get("equipment_slots", []),
        carry=inventory.get("carry", ["pocket"]),
        pickup_range=inventory.get("pickup_range", 4.0),
        state_numbers=movement.get("numbers", {}),
        state_flags=movement.get("flags", []),
        state_texts=movement.get("texts", {}),
        states_per_second=movement.get("per_second", 20.0),
        chat_max_length=chat.get("max_length", 200),
        chat_per_second=chat.get("per_second", 2.0),
    )
    for slot in RULES.carry:
        if slot != "pocket" and slot not in RULES.equipment_slots:
            raise ValueError(f"game.json: inventory.carry lists '{slot}', which is not an equipment slot")
    ITEMS.clear()
    for entry in json.loads(raw_items).get("items", []):
        ITEMS[entry["id"]] = _item(entry)
    content_hash = hashlib.sha256(raw_game + raw_items).hexdigest()[:16]
    log.info("Content loaded: %d items, %d equipment slots (hash %s)", len(ITEMS), len(RULES.equipment_slots), content_hash)
