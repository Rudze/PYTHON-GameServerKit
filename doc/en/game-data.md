# Game data

What changes from one game to the next is in two files of the `data/` folder (`DATA_DIR`), read when the game server starts. An invalid file stops the server from starting (with the error in the logs). After a change: restart the server, and put the same copy in the client.

## game.json: the rules

```json
{
  "zones": {"default": "world", "list": ["world", "forest", "dungeon_01"], "client_travel": true},
  "character": {"health": 100, "stamina": 100, "max_level": 50, "exp_per_level": 100},
  "appearance": {"parts": ["hair", "beard", "eyes", "skin"], "numbers": {"height": [0.0, 1.0], "build": [0.0, 1.0]}},
  "inventory": {
    "pocket": [4, 8],
    "equipment_slots": ["head", "chest", "legs", "feet", "back", "main_hand", "off_hand"],
    "carry": ["pocket", "back"],
    "pickup_range": 4.0
  },
  "movement": {
    "numbers": {"x": 100000, "y": 100000, "z": 100000, "rot": 1000, "speed": 50, "vy": 100},
    "flags": ["air", "crouch"],
    "texts": {"anim": 32},
    "per_second": 20
  },
  "chat": {"max_length": 200, "per_second": 2}
}
```

| Key | Default | Role |
|---|---|---|
| `zones.default` | `"world"` | The zone of a new player (or of a player whose zone no longer exists) |
| `zones.list` | `[]` | The possible zones; empty = any id (letters, digits, `_ : -`, 64 max) |
| `zones.client_travel` | `true` | May the client ask to change zone (`travel`)? `false`: only server code moves players |
| `character.health`, `stamina` | `100` | The maximums |
| `character.max_level` | `100` | Highest level |
| `character.exp_per_level` | `100` | Exp to the next level = `exp_per_level × level` |
| `appearance.parts` | `[]` | The parts that take an id (`"hair": "short_01"`) |
| `appearance.numbers` | `{}` | The number settings and their bounds `[min, max]` |
| `inventory.pocket` | `[2, 8]` | Rows and columns of the pocket |
| `inventory.equipment_slots` | `[]` | The equipment slots, one item each |
| `inventory.carry` | `["pocket"]` | Where picked up items go, in order: the pocket, then the inside of what is worn in the listed slots (a backpack...) |
| `inventory.pickup_range` | `4.0` | Distance in meters to pick up, drop, open a ground item; `0` = no limit |
| `movement.numbers` | `{}` | The state numbers and their largest absolute value. Include `x`, `y`, `z` and `rot` so the position is kept |
| `movement.flags` | `[]` | The state booleans |
| `movement.texts` | `{}` | The state short texts and their longest length |
| `movement.per_second` | `20` | States per second per player, at most |
| `chat.max_length` | `200` | Longest message |
| `chat.per_second` | `2` | Messages per second per player, at most |

## items.json: the items

```json
{
  "items": [
    {"id": "stone", "name": "Stone", "stackable": true, "max_stack": 50},
    {"id": "iron_sword", "name": "Iron sword", "width": 1, "height": 3, "equip_slot": "main_hand"},
    {"id": "health_potion", "name": "Health potion", "stackable": true, "max_stack": 10, "provides": ["potion"]},
    {"id": "small_backpack", "name": "Small backpack", "width": 3, "height": 3, "equip_slot": "back",
     "container": {"kind": "grid", "rows": 4, "cols": 5}},
    {"id": "potion_belt", "name": "Potion belt", "width": 2, "height": 1, "equip_slot": "legs",
     "container": {"kind": "slots", "slots": [{"name": "left", "accepts": ["potion"]}, {"name": "right", "accepts": ["potion"]}]}}
  ]
}
```

| Field | Default | Role |
|---|---|---|
| `id` | **required** | Unique id, used everywhere (saves, messages) |
| `width`, `height` | `1` | Cells taken in a grid (before rotation) |
| `stackable` | `false` | Several in one cell |
| `max_stack` | `1` | Largest stack |
| `equip_slot` | `""` | The equipment slot it goes in |
| `provides` | `[]` | Its tags (`"potion"`, `"arrow"`...), for filtering containers |
| `container` | none | What it holds: see below |

**Every other field** (`name`, `icon`, `description`, `damage`, `weight`, `price`...) is free: the server keeps it in `content.ITEMS[id]` for your code, and the client reads it from its copy.

### Containers

| `container` | Example | Role |
|---|---|---|
| `{"kind": "grid", "rows": 4, "cols": 5, "accepts": []}` | Bag, chest, quiver (`"accepts": ["arrow"]`) | A grid like the pocket |
| `{"kind": "slots", "slots": [{"name": "left", "accepts": ["potion"]}]}` | Belt, holster, key ring | Named slots, one item each |

`accepts`: an item goes in if its `provides` has at least one of these tags; empty or missing = any item. An item cannot go inside itself, nor inside what it holds.

### Removing an item

An item removed from `items.json` disappears from inventories and the ground on the next load (with a log message). Renaming an `id` is removing it.

## The fingerprint (content_hash)

`content_hash` = the first 16 hexadecimal characters of the SHA-256 of `game.json` followed by `items.json` (the exact bytes of the files). The server sends it in `welcome`; the client may send it in `auth`. With `REQUIRE_CONTENT_HASH=true`, a client with different data is refused: handy to force a game update. The Godot side is in [Godot integration](godot.md#the-data-fingerprint-content_hash).
