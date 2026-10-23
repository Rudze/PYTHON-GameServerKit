# Protocole WebSocket

Adresse par défaut : `ws://127.0.0.1:5001` (le `host` et le `port` donnés par `GET /servers/best`).

Chaque message est un objet JSON texte avec un champ `"type"`. Les messages du client sont refusés s'ils font plus de 64 Ko, et au-delà de 30 par seconde en moyenne (60 d'un coup), les messages en trop sont ignorés sans réponse.

## Sommaire

| Client → serveur | Serveur → client |
|---|---|
| [auth](#connexion) | [welcome](#connexion), [error](#erreurs) |
| [ping](#ping) | [pong](#ping) |
| [request_stats](#personnage) | [stats](#personnage) |
| [leave_world, spawn, set_name, set_appearance](#créateur-de-personnage) | [appearance](#créateur-de-personnage) |
| [state](#déplacements) | [player_state](#déplacements) |
| [travel](#changer-de-zone) | [change_location](#changer-de-zone) |
| — | [player_joined, player_left, player_look](#les-autres-joueurs) |
| [chat](#chat) | [chat](#chat) |
| [request_inventory, move_item, quick_move](#inventaire) | [inventory](#inventaire) |
| [open_container, close_container](#sacs-coffres-ceintures) | [container, container_closed](#sacs-coffres-ceintures) |
| [request_world_items, drop_item, pick_up](#objets-au-sol) | [world_items, world_item_added, world_item_updated, world_item_removed](#objets-au-sol) |

---

## Connexion

Le premier message, dans les 10 secondes :

```json
{"type": "auth", "token": "eyJ...", "content_hash": "f92c0370ea039f9b"}
```

| Champ | Rôle |
|---|---|
| `token` | Le jeton de `POST /auth/login` |
| `content_hash` | Optionnel : l'empreinte des données du jeu du client (voir [Données du jeu](game-data.md#lempreinte-content_hash)). Avec `REQUIRE_CONTENT_HASH=true`, un client dont l'empreinte diffère est refusé |

Le serveur répond, dans l'ordre :

1. `welcome`
   ```json
   {"type": "welcome", "user_id": 1, "username": "player_one", "is_admin": false, "server": "main",
    "content_hash": "f92c0370ea039f9b", "location": "world", "position": {"x": 1.0, "y": 0.0, "z": 2.0, "rot": 0.0},
    "appearance": {"hair": "short_01"}}
   ```
   `location` : la zone où charger le joueur. `position` : où il était (`null` : au point d'apparition de la zone).
2. `stats`, puis `inventory`.
3. Un `player_joined` par joueur déjà dans la zone.

Le client charge alors la zone, place son personnage, puis envoie `request_world_items`.

Connexion refusée : un message `error` puis la fermeture. Codes : `auth_required`, `invalid_token`, `content_mismatch`, `server_full`.

Si le même compte se connecte ailleurs, l'ancienne connexion reçoit `{"type": "error", "code": "replaced"}` et est fermée.

## Ping

```json
{"type": "ping", "time": 1234.5}      →      {"type": "pong", "time": 1234.5}
```

`time` est renvoyé tel quel : de quoi mesurer la latence. Le ping ne compte pas dans la limite de messages.

## Personnage

`{"type": "request_stats"}` → (et aussi à chaque changement, tout seul) :

```json
{"type": "stats", "name": "Player One",
 "health": {"value": 80, "max": 100}, "stamina": {"value": 100, "max": 100},
 "progression": {"level": 3, "exp": 40, "exp_next": 300}}
```

## Créateur de personnage

Le joueur doit sortir du monde pour changer son nom ou son apparence (les autres ne le voient plus pendant ce temps) :

| Message | Effet |
|---|---|
| `{"type": "leave_world"}` | Les autres reçoivent `player_left` |
| `{"type": "set_name", "name": "Player One"}` | 3 à 16 lettres (tous alphabets), chiffres, espaces, `'` ou `-` ; réponse : `stats` |
| `{"type": "set_appearance", "parts": {"hair": "short_01", "beard": "", "height": 0.4}}` | Seules les entrées données changent ; réponse : `{"type": "appearance", "appearance": {...}}` |
| `{"type": "spawn"}` | Retour dans le monde : les autres reçoivent `player_joined` |

Dans `parts`, une **partie** (liste `appearance.parts` de `game.json`) prend un id (`a-z`, `0-9`, `_`, 64 max ; `""` = aucune), un **nombre** (`appearance.numbers`) une valeur entre son min et son max. Erreurs : `not_in_creator`, `invalid_name`, `invalid_appearance`.

Hors du monde, seuls `request_stats`, `set_name`, `set_appearance`, `spawn` et `ping` sont traités.

## Déplacements

Le client envoie l'état de son personnage pendant qu'il bouge (20 fois par seconde au plus, `movement.per_second`) :

```json
{"type": "state", "location": "world", "x": 1.0, "y": 0.0, "z": 2.0, "rot": 1.57, "speed": 3.2, "vy": 0.0,
 "air": false, "crouch": false, "anim": "run"}
```

Les champs sont ceux de `movement` dans `game.json` : nombres (bornés à leur limite, tous obligatoires), drapeaux (`true` ou `false`), textes courts. `location` doit être la zone actuelle (un état envoyé juste avant un changement de zone est ignoré). `x`, `y`, `z`, `rot` sont gardés comme position du joueur (reconnexion, distance aux objets au sol).

Les autres joueurs de la zone reçoivent :

```json
{"type": "player_state", "user_id": 2, "state": {"x": 1.0, "y": 0.0, "z": 2.0, "rot": 1.57, "speed": 3.2, "vy": 0.0, "air": false, "crouch": false, "anim": "run"}}
```

Le serveur relaie, il ne simule pas la physique : le client interpole entre deux états.

## Changer de zone

```json
{"type": "travel", "location": "forest"}
```

→ `{"type": "change_location", "location": "forest", "position": null}` : le client charge la zone. Les joueurs de l'ancienne zone reçoivent `player_left`, ceux de la nouvelle `player_joined` (et le joueur reçoit un `player_joined` par joueur déjà là).

Erreurs : `unknown_location` (pas dans `zones.list`), `travel_refused` (`zones.client_travel` vaut `false` : seul le serveur déplace les joueurs, par exemple avec un portail vérifié côté serveur). Un `change_location` peut aussi arriver sans demande (téléportation décidée par le serveur).

## Les autres joueurs

```json
{"type": "player_joined", "user_id": 2, "name": "Player Two", "appearance": {"hair": "long_02"},
 "worn": {"head": "leather_cap", "back": "small_backpack"},
 "position": {"x": 5.0, "y": 0.0, "z": 1.0, "rot": 0.0}, "state": {}}

{"type": "player_left", "user_id": 2}

{"type": "player_look", "user_id": 2, "appearance": {...}, "worn": {"head": "leather_cap"}}
```

`worn` : l'objet porté dans chaque emplacement d'équipement (pour afficher le casque, le sac...). `player_look` arrive quand il change. `position` peut être `null` (au point d'apparition), `state` vide (immobile).

## Chat

```json
{"type": "chat", "message": "salut", "channel": "local"}
```

`channel` : `"local"` (la zone, par défaut) ou `"global"` (tout le serveur). Tout le monde, l'envoyeur compris, reçoit :

```json
{"type": "chat", "channel": "local", "user_id": 1, "name": "Player One", "message": "salut"}
```

Les espaces et retours à la ligne en trop sont retirés. Erreurs : `chat_too_long` (`chat.max_length`), `chat_too_fast` (`chat.per_second`).

## Inventaire

### Les adresses

Un message d'inventaire désigne un conteneur par son **adresse** et une place par sa **clé** :

| Adresse | Conteneur | Clé |
|---|---|---|
| `"pocket"` | La poche du joueur (une grille) | L'index de la case en haut à gauche : `ligne * cols + colonne` |
| `"head"`, `"back"`... | Un emplacement d'équipement (`inventory.equipment_slots`) | Toujours `0` |
| `"<uid d'un objet>"` | L'intérieur d'un sac, d'un coffre, d'une ceinture porté ou au sol à portée | Un index (grille) ou un nom d'emplacement (`"left"`) |

### Un objet

```json
{"uid": "1bd9611f61424480862f940f7095a1c7", "item_id": "stone", "quantity": 15, "rotated": false,
 "width": 1, "height": 1, "container_kind": null, "data": {"quantity": 15}}
```

`width` et `height` tiennent compte de la rotation. `container_kind` : `"grid"`, `"slots"` ou `null`. Le nom, l'icône, la description viennent du `items.json` du client (même `item_id`). `data` : les données propres à cet objet (quantité, rotation, et tout ce que votre jeu ajoute).

### inventory

`{"type": "request_inventory"}`, et après chaque changement :

```json
{"type": "inventory", "containers": {
  "pocket": {"rows": 4, "cols": 8, "equip_slot": "", "items": {"0": {...}, "5": {...}}},
  "head":   {"rows": 1, "cols": 1, "equip_slot": "head", "items": {}},
  "back":   {"rows": 1, "cols": 1, "equip_slot": "back", "items": {"0": {...}}}
}}
```

### move_item

D'un conteneur à un autre (ou dans le même) :

```json
{"type": "move_item", "from_container": "pocket", "from": 0, "to_container": "back", "to": 0, "rotate": false, "split": false}
```

| Cas | Effet |
|---|---|
| Place libre | L'objet y va (`rotate: true` le tourne d'un quart de tour) |
| Même objet empilable à l'arrivée | Les piles fusionnent (le reste reste au départ) |
| `split: true` sur une pile | La moitié va à l'arrivée |
| Emplacement d'équipement | Seulement un objet dont `equip_slot` est ce nom |

Erreurs : `not_found`, `invalid_move` (le message dit pourquoi : place prise, hors grille, objet dans lui-même, objet refusé...), `stack_full`.

### quick_move

Ctrl + clic : `{"type": "quick_move", "container": "pocket", "key": 3}`. Depuis les conteneurs du joueur, l'objet va dans le premier conteneur ouvert qui a de la place ; depuis ailleurs, il revient dans ce que le joueur porte (`inventory.carry`). Erreur : `no_room`.

## Sacs, coffres, ceintures

```json
{"type": "open_container", "uid": "9865a810b338710deed154e16793ee30"}
```

L'objet doit être porté, ou au sol à portée (`inventory.pickup_range`). Réponse (et à chaque changement tant qu'il est ouvert, même par un autre joueur) :

```json
{"type": "container", "uid": "9865...", "item_id": "small_backpack", "kind": "grid", "rows": 4, "cols": 5,
 "items": {"0": {...}}}

{"type": "container", "uid": "...", "item_id": "potion_belt", "kind": "slots",
 "slots": [{"name": "left", "accepts": ["potion"]}, {"name": "right", "accepts": ["potion"]}],
 "items": {"left": {...}}}
```

`{"type": "close_container", "uid": "..."}` arrête les mises à jour. Le serveur envoie `{"type": "container_closed", "uid": "..."}` quand le conteneur n'est plus accessible (ramassé par un autre, trop loin, détruit).

## Objets au sol

`{"type": "request_world_items"}` (après avoir chargé une zone) :

```json
{"type": "world_items", "location": "world", "items": [
  {"uid": "...", "item_id": "stone", "quantity": 15, "rotated": false, "width": 1, "height": 1,
   "container_kind": null, "data": {...}, "x": 0.0, "y": 0.0, "z": 0.0, "rot": 0.0}
]}
```

| Message | Effet |
|---|---|
| `{"type": "drop_item", "from_container": "pocket", "from": 0, "x": 1.0, "y": 0.0, "z": 2.0, "rot": 0.0}` | Pose l'objet (avec son contenu) près du joueur. Toute la zone reçoit `world_item_added` |
| `{"type": "pick_up", "uid": "..."}` | Ramasse dans ce que le joueur porte (poche, puis sac porté...). Toute la zone reçoit `world_item_removed` |
| `{"type": "pick_up", "uid": "...", "equip": true}` | Ramasse directement dans son emplacement d'équipement |

Une pile ramassée en partie (plus de place) reste au sol avec la quantité restante : `world_item_updated` avec l'objet à jour. Erreurs : `not_found`, `too_far`, `no_room`, `cannot_equip`.

```json
{"type": "world_item_added", "item": {...}}
{"type": "world_item_updated", "item": {...}}
{"type": "world_item_removed", "uid": "..."}
```

## Erreurs

```json
{"type": "error", "code": "no_room", "message": "No room for this item"}
```

`message` est en anglais, pour les logs ; affichez au joueur un texte choisi selon `code`.

| Code | Quand |
|---|---|
| `auth_required`, `invalid_token`, `content_mismatch`, `server_full` | Connexion refusée (puis fermeture) |
| `replaced` | Le même compte s'est connecté ailleurs (puis fermeture) |
| `invalid_json`, `unknown_type` | Message illisible ou type inconnu |
| `server_error` | Bug côté serveur (détails dans ses logs) |
| `unknown_location`, `travel_refused` | Changement de zone refusé |
| `chat_too_long`, `chat_too_fast` | Chat |
| `not_in_creator`, `invalid_name`, `invalid_appearance` | Créateur de personnage |
| `not_found`, `invalid_move`, `stack_full`, `no_room`, `too_far`, `cannot_equip` | Inventaire, objets au sol |
