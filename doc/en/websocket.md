# WebSocket protocol

Default address: `ws://127.0.0.1:5001` (the `host` and `port` given by `GET /servers/best`).

Every message is a text JSON object with a `"type"` field. Client messages are refused above 64 KB, and above 30 per second on average (60 at once) the extra messages are dropped without an answer.

## Summary

| Client → server | Server → client |
|---|---|
| [auth](#connection) | [welcome](#connection), [error](#errors) |
| [ping](#ping) | [pong](#ping) |
| [request_stats](#character) | [stats](#character) |
| [leave_world, spawn, set_name, set_appearance](#character-creator) | [appearance](#character-creator) |
| [state](#movement) | [player_state](#movement) |
| [travel](#changing-zone) | [change_location](#changing-zone) |
| — | [player_joined, player_left, player_look](#the-other-players) |
| [chat](#chat) | [chat](#chat) |
| [request_inventory, move_item, quick_move](#inventory) | [inventory](#inventory) |
| [open_container, close_container](#bags-chests-belts) | [container, container_closed](#bags-chests-belts) |
| [request_world_items, drop_item, pick_up](#items-on-the-ground) | [world_items, world_item_added, world_item_updated, world_item_removed](#items-on-the-ground) |

---

## Connection

The first message, within 10 seconds:

```json
{"type": "auth", "token": "eyJ...", "content_hash": "f92c0370ea039f9b"}
```

| Field | Role |
|---|---|
| `token` | The token from `POST /auth/login` |
| `content_hash` | Optional: the fingerprint of the client's game data (see [Game data](game-data.md#the-fingerprint-content_hash)). With `REQUIRE_CONTENT_HASH=true`, a client whose fingerprint differs is refused |

The server answers, in order:

1. `welcome`
   ```json
   {"type": "welcome", "user_id": 1, "username": "player_one", "is_admin": false, "server": "main",
    "content_hash": "f92c0370ea039f9b", "location": "world", "position": {"x": 1.0, "y": 0.0, "z": 2.0, "rot": 0.0},
    "appearance": {"hair": "short_01"}}
   ```
   `location`: the zone to load the player in. `position`: where they were (`null`: at the zone's spawn).
2. `stats`, then `inventory`.
3. One `player_joined` per player already in the zone.

The client then loads the zone, places its character, then sends `request_world_items`.

Refused connection: an `error` message then the connection closes. Codes: `auth_required`, `invalid_token`, `content_mismatch`, `server_full`.

If the same account connects somewhere else, the old connection gets `{"type": "error", "code": "replaced"}` and is closed.

## Ping

```json
{"type": "ping", "time": 1234.5}      →      {"type": "pong", "time": 1234.5}
```

`time` comes back as is: enough to measure latency. Pings do not count toward the message limit.

## Character

`{"type": "request_stats"}` → (and on every change, on its own):

```json
{"type": "stats", "name": "Player One",
 "health": {"value": 80, "max": 100}, "stamina": {"value": 100, "max": 100},
 "progression": {"level": 3, "exp": 40, "exp_next": 300}}
```

## Character creator

The player must leave the world to change their name or look (the others stop seeing them meanwhile):

| Message | Effect |
|---|---|
| `{"type": "leave_world"}` | The others get `player_left` |
| `{"type": "set_name", "name": "Player One"}` | 3 to 16 letters (any alphabet), digits, spaces, `'` or `-`; answer: `stats` |
| `{"type": "set_appearance", "parts": {"hair": "short_01", "beard": "", "height": 0.4}}` | Only the given entries change; answer: `{"type": "appearance", "appearance": {...}}` |
| `{"type": "spawn"}` | Back in the world: the others get `player_joined` |

In `parts`, a **part** (list `appearance.parts` of `game.json`) takes an id (`a-z`, `0-9`, `_`, 64 max; `""` = none), a **number** (`appearance.numbers`) a value between its min and max. Errors: `not_in_creator`, `invalid_name`, `invalid_appearance`.

Out of the world, only `request_stats`, `set_name`, `set_appearance`, `spawn` and `ping` are handled.

## Movement

The client sends its character's state while it moves (20 times per second at most, `movement.per_second`):

```json
{"type": "state", "location": "world", "x": 1.0, "y": 0.0, "z": 2.0, "rot": 1.57, "speed": 3.2, "vy": 0.0,
 "air": false, "crouch": false, "anim": "run"}
```

The fields are those of `movement` in `game.json`: numbers (clamped to their limit, all required), flags (`true` or `false`), short texts. `location` must be the current zone (a state sent just before a zone change is ignored). `x`, `y`, `z`, `rot` are kept as the player's position (reconnection, distance to ground items).

The other players of the zone get:

```json
{"type": "player_state", "user_id": 2, "state": {"x": 1.0, "y": 0.0, "z": 2.0, "rot": 1.57, "speed": 3.2, "vy": 0.0, "air": false, "crouch": false, "anim": "run"}}
```

The server relays, it does not simulate physics: the client interpolates between two states.

## Changing zone

```json
{"type": "travel", "location": "forest"}
```

→ `{"type": "change_location", "location": "forest", "position": null}`: the client loads the zone. The players of the old zone get `player_left`, those of the new one `player_joined` (and the player gets one `player_joined` per player already there).

Errors: `unknown_location` (not in `zones.list`), `travel_refused` (`zones.client_travel` is `false`: only the server moves players, for example through a portal checked server side). A `change_location` can also arrive unasked (a teleport decided by the server).

## The other players

```json
{"type": "player_joined", "user_id": 2, "name": "Player Two", "appearance": {"hair": "long_02"},
 "worn": {"head": "leather_cap", "back": "small_backpack"},
 "position": {"x": 5.0, "y": 0.0, "z": 1.0, "rot": 0.0}, "state": {}}

{"type": "player_left", "user_id": 2}

{"type": "player_look", "user_id": 2, "appearance": {...}, "worn": {"head": "leather_cap"}}
```

`worn`: the item worn in each equipment slot (to show the helmet, the bag...). `player_look` arrives when it changes. `position` can be `null` (at the spawn), `state` empty (standing still).

## Chat

```json
{"type": "chat", "message": "hi", "channel": "local"}
```

`channel`: `"local"` (the zone, default) or `"global"` (the whole server). Everyone, the sender included, gets:

```json
{"type": "chat", "channel": "local", "user_id": 1, "name": "Player One", "message": "hi"}
```

Extra spaces and line breaks are removed. Errors: `chat_too_long` (`chat.max_length`), `chat_too_fast` (`chat.per_second`).

## Inventory

### Addresses

An inventory message names a container by its **address** and a place by its **key**:

| Address | Container | Key |
|---|---|---|
| `"pocket"` | The player's pocket (a grid) | The index of the top-left cell: `row * cols + column` |
| `"head"`, `"back"`... | An equipment slot (`inventory.equipment_slots`) | Always `0` |
| `"<an item uid>"` | The inside of a bag, chest, belt carried or on the ground within reach | An index (grid) or a slot name (`"left"`) |

### An item

```json
{"uid": "1bd9611f61424480862f940f7095a1c7", "item_id": "stone", "quantity": 15, "rotated": false,
 "width": 1, "height": 1, "container_kind": null, "data": {"quantity": 15}}
```

`width` and `height` include the rotation. `container_kind`: `"grid"`, `"slots"` or `null`. The name, icon, description come from the client's `items.json` (same `item_id`). `data`: the data of this very item (quantity, rotation, and anything your game adds).

### inventory

`{"type": "request_inventory"}`, and after every change:

```json
{"type": "inventory", "containers": {
  "pocket": {"rows": 4, "cols": 8, "equip_slot": "", "items": {"0": {...}, "5": {...}}},
  "head":   {"rows": 1, "cols": 1, "equip_slot": "head", "items": {}},
  "back":   {"rows": 1, "cols": 1, "equip_slot": "back", "items": {"0": {...}}}
}}
```

### move_item

From one container to another (or within one):

```json
{"type": "move_item", "from_container": "pocket", "from": 0, "to_container": "back", "to": 0, "rotate": false, "split": false}
```

| Case | Effect |
|---|---|
| Free room | The item goes there (`rotate: true` turns it a quarter turn) |
| Same stackable item at the target | The stacks merge (the rest stays at the source) |
| `split: true` on a stack | Half of it goes to the target |
| Equipment slot | Only an item whose `equip_slot` is that name |

Errors: `not_found`, `invalid_move` (the message says why: room taken, out of the grid, item inside itself, item refused...), `stack_full`.

### quick_move

Ctrl + click: `{"type": "quick_move", "container": "pocket", "key": 3}`. From the player's own containers, the item goes to the first open container with room; from anywhere else, it comes back into what the player carries (`inventory.carry`). Error: `no_room`.

## Bags, chests, belts

```json
{"type": "open_container", "uid": "9865a810b338710deed154e16793ee30"}
```

The item must be carried, or on the ground within reach (`inventory.pickup_range`). Answer (and on every change while it is open, even by another player):

```json
{"type": "container", "uid": "9865...", "item_id": "small_backpack", "kind": "grid", "rows": 4, "cols": 5,
 "items": {"0": {...}}}

{"type": "container", "uid": "...", "item_id": "potion_belt", "kind": "slots",
 "slots": [{"name": "left", "accepts": ["potion"]}, {"name": "right", "accepts": ["potion"]}],
 "items": {"left": {...}}}
```

`{"type": "close_container", "uid": "..."}` stops the updates. The server sends `{"type": "container_closed", "uid": "..."}` when the container is no longer reachable (picked up by someone else, too far, destroyed).

## Items on the ground

`{"type": "request_world_items"}` (after loading a zone):

```json
{"type": "world_items", "location": "world", "items": [
  {"uid": "...", "item_id": "stone", "quantity": 15, "rotated": false, "width": 1, "height": 1,
   "container_kind": null, "data": {...}, "x": 0.0, "y": 0.0, "z": 0.0, "rot": 0.0}
]}
```

| Message | Effect |
|---|---|
| `{"type": "drop_item", "from_container": "pocket", "from": 0, "x": 1.0, "y": 0.0, "z": 2.0, "rot": 0.0}` | Puts the item (with its contents) near the player. The whole zone gets `world_item_added` |
| `{"type": "pick_up", "uid": "..."}` | Picks it up into what the player carries (pocket, then worn bag...). The whole zone gets `world_item_removed` |
| `{"type": "pick_up", "uid": "...", "equip": true}` | Picks it up straight into its equipment slot |

A stack partly picked up (no more room) stays on the ground with the quantity left: `world_item_updated` with the updated item. Errors: `not_found`, `too_far`, `no_room`, `cannot_equip`.

```json
{"type": "world_item_added", "item": {...}}
{"type": "world_item_updated", "item": {...}}
{"type": "world_item_removed", "uid": "..."}
```

## Errors

```json
{"type": "error", "code": "no_room", "message": "No room for this item"}
```

`message` is in English, for logs; show the player a text chosen from `code`.

| Code | When |
|---|---|
| `auth_required`, `invalid_token`, `content_mismatch`, `server_full` | Connection refused (then closed) |
| `replaced` | The same account connected somewhere else (then closed) |
| `invalid_json`, `unknown_type` | Unreadable message or unknown type |
| `server_error` | A server bug (details in its logs) |
| `unknown_location`, `travel_refused` | Zone change refused |
| `chat_too_long`, `chat_too_fast` | Chat |
| `not_in_creator`, `invalid_name`, `invalid_appearance` | Character creator |
| `not_found`, `invalid_move`, `stack_full`, `no_room`, `too_far`, `cannot_equip` | Inventory, items on the ground |
