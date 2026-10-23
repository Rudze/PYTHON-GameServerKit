# Godot integration

A complete Godot 4 client in three pieces:

| File | Role |
|---|---|
| `api.gd` (autoload `Api`) | The HTTP calls: account, login, server choice — see [HTTP API](http-api.md#from-godot-gdscript) |
| `game.gd` (autoload `Game`) | The WebSocket connection: sends messages, receives and dispatches the answers through signals |
| Your scenes | Listen to `Game`'s signals (chat, players, inventory...) and call its functions |

## game.gd

```gdscript
extends Node

signal connected(welcome: Dictionary)
signal disconnected(reason: String)
signal message_received(message: Dictionary)   # every message
signal error_received(code: String, text: String)

const STATE_INTERVAL := 0.05   # 20 states per second at most (movement.per_second in game.json)

var socket := WebSocketPeer.new()
var token := ""
var online := false
var _authenticated := false
var _handlers := {}             # type -> Array[Callable]


# ---
func connect_to_server(host: String, port: int, access_token: String) -> void:
	token = access_token
	_authenticated = false
	online = false
	socket = WebSocketPeer.new()
	socket.connect_to_url("ws://%s:%d" % [host, port])


# ---
func send(message: Dictionary) -> void:
	if socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
		socket.send_text(JSON.stringify(message))


# ---
## Calls `callback(message)` for every message of this type.
func on(type: String, callback: Callable) -> void:
	_handlers.get_or_add(type, []).append(callback)


# ---
func _process(_delta: float) -> void:
	socket.poll()
	match socket.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			if not _authenticated:
				_authenticated = true
				send({"type": "auth", "token": token, "content_hash": ContentHash.compute()})
			while socket.get_available_packet_count() > 0:
				var message = JSON.parse_string(socket.get_packet().get_string_from_utf8())
				if message is Dictionary:
					_dispatch(message)
		WebSocketPeer.STATE_CLOSED:
			if _authenticated:
				_authenticated = false
				online = false
				disconnected.emit(socket.get_close_reason())


# ---
func _dispatch(message: Dictionary) -> void:
	match message.type:
		"welcome":
			online = true
			connected.emit(message)
		"error":
			error_received.emit(message.code, message.message)
	message_received.emit(message)
	for callback in _handlers.get(message.type, []):
		callback.call(message)
```

## Connecting

```gdscript
func _on_play_pressed() -> void:
	if not await Api.login(username_edit.text, password_edit.text):
		show_error("Wrong username or password")
		return
	var server := await Api.best_server()
	if server.is_empty():
		show_error("No server available")
		return
	Game.connected.connect(_on_connected, CONNECT_ONE_SHOT)
	Game.connect_to_server(server.host, server.port, Api.token)


func _on_connected(welcome: Dictionary) -> void:
	# Load the zone, then place the player at welcome.position (null: the spawn)
	await World.load_zone(welcome.location)
	Player.place_at(welcome.position)
	Game.send({"type": "request_world_items"})
```

The `player_joined` messages arrive right after `welcome`, while the zone loads: keep them aside and create the characters once the zone is ready.

## Sending movement

```gdscript
var _since_last_state := 0.0

func _physics_process(delta: float) -> void:
	_since_last_state += delta
	if _since_last_state < Game.STATE_INTERVAL or not Game.online:
		return
	_since_last_state = 0.0
	Game.send({
		"type": "state", "location": World.location,
		"x": global_position.x, "y": global_position.y, "z": global_position.z, "rot": rotation.y,
		"speed": velocity.length(), "vy": velocity.y,
		"air": not is_on_floor(), "crouch": is_crouching, "anim": current_anim,
	})
```

The fields must be those of `movement` in `game.json` (every number is required).

## Showing the other players

```gdscript
var others := {}   # user_id -> character


func _ready() -> void:
	Game.on("player_joined", _on_player_joined)
	Game.on("player_left", _on_player_left)
	Game.on("player_state", _on_player_state)


func _on_player_joined(message: Dictionary) -> void:
	var character: RemoteCharacter = preload("res://characters/remote_character.tscn").instantiate()
	add_child(character)
	character.setup(message.name, message.appearance, message.worn, message.position)
	others[int(message.user_id)] = character


func _on_player_left(message: Dictionary) -> void:
	var character = others.get(int(message.user_id))
	if character:
		character.queue_free()
		others.erase(int(message.user_id))


func _on_player_state(message: Dictionary) -> void:
	var character = others.get(int(message.user_id))
	if character:
		character.target_state = message.state   # the character interpolates toward this state
```

JSON numbers arrive as `float` in Godot: `int(message.user_id)` for the keys.

## Chat

```gdscript
func _ready() -> void:
	Game.on("chat", func(message): chat_log.append_text("[%s] %s\n" % [message.name, message.message]))


func _on_chat_submitted(text: String) -> void:
	Game.send({"type": "chat", "message": text, "channel": "local"})
```

## Inventory

```gdscript
func _ready() -> void:
	Game.on("inventory", _on_inventory)
	Game.send({"type": "request_inventory"})


func _on_inventory(message: Dictionary) -> void:
	var pocket: Dictionary = message.containers.pocket
	grid_view.build(pocket.rows, pocket.cols)
	for key in pocket.items:
		var item: Dictionary = pocket.items[key]
		var definition: Dictionary = Items.get_definition(item.item_id)   # from your items.json
		grid_view.show_item(int(key), item.width, item.height, definition.icon, item.quantity)


## Drag and drop from the pocket to the worn bag (its uid is containers.back.items["0"].uid)
func _on_item_dropped(from_key: int, bag_uid: String, to_key: int) -> void:
	Game.send({"type": "move_item", "from_container": "pocket", "from": from_key,
		"to_container": bag_uid, "to": to_key})
```

The server decides: do not show the move as done before the new `inventory` arrives (or show it, and roll back on an `error`).

## The data fingerprint (content_hash)

Client and server must have the same `game.json` and `items.json`. Copy them into the Godot project (for example `res://data/`), and compute the same fingerprint as the server:

```gdscript
class_name ContentHash


# ---
## sha256(game.json + items.json), first 16 hexadecimal characters: like server/content.py.
static func compute() -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(FileAccess.get_file_as_bytes("res://data/game.json"))
	context.update(FileAccess.get_file_as_bytes("res://data/items.json"))
	return context.finish().hex_encode().substr(0, 16)
```

Add `*.json` to the export filters (Project > Export > Resources) so they are in the exported game.
