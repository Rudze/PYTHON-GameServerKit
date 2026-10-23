# Données du jeu

Ce qui change d'un jeu à l'autre est dans deux fichiers du dossier `data/` (`DATA_DIR`), lus au démarrage du serveur de jeu. Un fichier invalide empêche le serveur de démarrer (avec l'erreur dans les logs). Après un changement : redémarrez le serveur, et mettez la même copie dans le client.

## game.json : les règles

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

| Clé | Défaut | Rôle |
|---|---|---|
| `zones.default` | `"world"` | La zone d'un nouveau joueur (ou d'un joueur dont la zone n'existe plus) |
| `zones.list` | `[]` | Les zones possibles ; vide = n'importe quel id (lettres, chiffres, `_ : -`, 64 max) |
| `zones.client_travel` | `true` | Le client peut-il demander à changer de zone (`travel`) ? `false` : seul le code serveur déplace les joueurs |
| `character.health`, `stamina` | `100` | Les maximums |
| `character.max_level` | `100` | Niveau maximum |
| `character.exp_per_level` | `100` | Exp pour passer au niveau suivant = `exp_per_level × niveau` |
| `appearance.parts` | `[]` | Les parties qui prennent un id (`"hair": "short_01"`) |
| `appearance.numbers` | `{}` | Les réglages numériques et leurs bornes `[min, max]` |
| `inventory.pocket` | `[2, 8]` | Lignes et colonnes de la poche |
| `inventory.equipment_slots` | `[]` | Les emplacements d'équipement, un objet chacun |
| `inventory.carry` | `["pocket"]` | Où vont les objets ramassés, dans l'ordre : la poche, puis l'intérieur de ce qui est porté dans les emplacements listés (un sac à dos...) |
| `inventory.pickup_range` | `4.0` | Distance en mètres pour ramasser, poser, ouvrir un objet au sol ; `0` = pas de limite |
| `movement.numbers` | `{}` | Les nombres de l'état et leur valeur absolue maximale. Mettez `x`, `y`, `z` et `rot` pour que la position soit gardée |
| `movement.flags` | `[]` | Les booléens de l'état |
| `movement.texts` | `{}` | Les textes courts de l'état et leur longueur maximale |
| `movement.per_second` | `20` | États au plus par seconde et par joueur |
| `chat.max_length` | `200` | Longueur maximale d'un message |
| `chat.per_second` | `2` | Messages au plus par seconde et par joueur |

## items.json : les objets

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

| Champ | Défaut | Rôle |
|---|---|---|
| `id` | **obligatoire** | Identifiant unique, utilisé partout (sauvegardes, messages) |
| `width`, `height` | `1` | Cases prises dans une grille (avant rotation) |
| `stackable` | `false` | Plusieurs exemplaires dans une case |
| `max_stack` | `1` | Taille maximale d'une pile |
| `equip_slot` | `""` | L'emplacement d'équipement où il va |
| `provides` | `[]` | Ses étiquettes (`"potion"`, `"arrow"`...), pour les conteneurs qui filtrent |
| `container` | aucun | Ce qu'il contient : voir plus bas |

**Tous les autres champs** (`name`, `icon`, `description`, `damage`, `weight`, `price`...) sont libres : le serveur les garde dans `content.ITEMS[id]` pour votre code, et le client les lit dans sa copie.

### Les conteneurs

| `container` | Exemple | Rôle |
|---|---|---|
| `{"kind": "grid", "rows": 4, "cols": 5, "accepts": []}` | Sac, coffre, carquois (`"accepts": ["arrow"]`) | Une grille comme la poche |
| `{"kind": "slots", "slots": [{"name": "left", "accepts": ["potion"]}]}` | Ceinture, holster, porte-clés | Des emplacements nommés, un objet chacun |

`accepts` : un objet entre s'il a dans `provides` au moins une de ces étiquettes ; vide ou absent = tout objet. Un objet ne peut pas entrer dans lui-même, ni dans ce qu'il contient.

### Retirer un objet

Un objet retiré de `items.json` disparaît des inventaires et du sol au prochain chargement (avec un message dans les logs). Renommer un `id` revient à le retirer.

## L'empreinte (content_hash)

`content_hash` = les 16 premiers caractères hexadécimaux du SHA-256 de `game.json` suivi de `items.json` (les octets exacts des fichiers). Le serveur l'envoie dans `welcome` ; le client peut l'envoyer dans `auth`. Avec `REQUIRE_CONTENT_HASH=true`, un client aux données différentes est refusé : pratique pour forcer une mise à jour du jeu. Le calcul côté Godot est dans [Intégration Godot](godot.md#lempreinte-des-données-content_hash).
