# Intégration Godot

Un client Godot 4 complet en trois morceaux :

| Fichier | Rôle |
|---|---|
| `api.gd` (autoload `Api`) | Les appels HTTP : compte, connexion, choix du serveur — voir [API HTTP](http-api.md#depuis-godot-gdscript) |
| `game.gd` (autoload `Game`) | La connexion WebSocket : envoie les messages, reçoit et distribue les réponses par signal |
| Vos scènes | Écoutent les signaux de `Game` (chat, joueurs, inventaire...) et appellent ses fonctions |

## game.gd

```gdscript
extends Node

signal connected(welcome: Dictionary)
signal disconnected(reason: String)
signal message_received(message: Dictionary)   # tous les messages
signal error_received(code: String, text: String)

const STATE_INTERVAL := 0.05   # 20 états par seconde au plus (movement.per_second de game.json)

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
## Appelle `callback(message)` pour chaque message de ce type.
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

## Se connecter

```gdscript
func _on_play_pressed() -> void:
	if not await Api.login(username_edit.text, password_edit.text):
		show_error("Mauvais nom ou mot de passe")
		return
	var server := await Api.best_server()
	if server.is_empty():
		show_error("Aucun serveur disponible")
		return
	Game.connected.connect(_on_connected, CONNECT_ONE_SHOT)
	Game.connect_to_server(server.host, server.port, Api.token)


func _on_connected(welcome: Dictionary) -> void:
	# Charger la zone, puis placer le joueur à welcome.position (null : point d'apparition)
	await World.load_zone(welcome.location)
	Player.place_at(welcome.position)
	Game.send({"type": "request_world_items"})
```

Les `player_joined` arrivent juste après `welcome`, pendant que la zone charge : gardez-les de côté et créez les personnages une fois la zone prête.

## Envoyer ses déplacements

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

Les champs doivent être ceux de `movement` dans `game.json` (tous les nombres sont obligatoires).

## Afficher les autres joueurs

```gdscript
var others := {}   # user_id -> personnage


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
		character.target_state = message.state   # le personnage interpole vers cet état
```

Les nombres JSON arrivent en `float` dans Godot : `int(message.user_id)` pour les clés.

## Le chat

```gdscript
func _ready() -> void:
	Game.on("chat", func(message): chat_log.append_text("[%s] %s\n" % [message.name, message.message]))


func _on_chat_submitted(text: String) -> void:
	Game.send({"type": "chat", "message": text, "channel": "local"})
```

## L'inventaire

```gdscript
func _ready() -> void:
	Game.on("inventory", _on_inventory)
	Game.send({"type": "request_inventory"})


func _on_inventory(message: Dictionary) -> void:
	var pocket: Dictionary = message.containers.pocket
	grid_view.build(pocket.rows, pocket.cols)
	for key in pocket.items:
		var item: Dictionary = pocket.items[key]
		var definition: Dictionary = Items.get_definition(item.item_id)   # depuis votre items.json
		grid_view.show_item(int(key), item.width, item.height, definition.icon, item.quantity)


## Glisser-déposer de la poche vers le sac porté (son uid vient de containers.back.items["0"].uid)
func _on_item_dropped(from_key: int, bag_uid: String, to_key: int) -> void:
	Game.send({"type": "move_item", "from_container": "pocket", "from": from_key,
		"to_container": bag_uid, "to": to_key})
```

Le serveur décide : n'affichez pas le déplacement comme fait avant d'avoir reçu le nouvel `inventory` (ou affichez-le, et revenez en arrière sur un `error`).

## L'empreinte des données (content_hash)

Le client et le serveur doivent avoir les mêmes `game.json` et `items.json`. Copiez-les dans le projet Godot (par exemple `res://data/`), et calculez la même empreinte que le serveur :

```gdscript
class_name ContentHash


# ---
## sha256(game.json + items.json), 16 premiers caractères hexadécimaux : comme server/content.py.
static func compute() -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(FileAccess.get_file_as_bytes("res://data/game.json"))
	context.update(FileAccess.get_file_as_bytes("res://data/items.json"))
	return context.finish().hex_encode().substr(0, 16)
```

Pensez à ajouter `*.json` aux filtres d'export (Projet > Exporter > Ressources) pour qu'ils soient dans le jeu exporté.
