# Étendre le kit

Le kit donne la base ; votre gameplay (combat, récolte, artisanat, quêtes, commerce...) s'ajoute en **modules**, sans modifier le cœur.

## Ajouter un module

Exemple : un message « manger » qui consomme un objet de la poche et rend de la vie.

**1.** Créez `server/modules/food.py` :

```python
"""Eating: {"type": "eat", "key": <pocket index>} consumes one food item and heals."""
from server.modules.inventory import handlers as inventory
from server.router import handler
from server.session import Session


@handler("eat")
async def on_eat(session: Session, data: dict):
    pocket = session.inventories["pocket"]
    item = pocket.slots.get(data.get("key"))
    heal = item.definition.get("heal", 0) if item else 0   # un champ libre de items.json
    if heal <= 0:
        await session.error("You cannot eat this", "not_food")
        return
    item.quantity -= 1
    if item.quantity <= 0:
        pocket.remove(data["key"])
    session.health.add(heal)                 # sauvegardé et envoyé ("stats") tout seul
    await inventory.after_change(session)    # inventaire sauvegardé et envoyé
```

**2.** Importez-le dans `server/modules/__init__.py` :

```python
from server.modules import character, chat, food, movement   # noqa: F401
```

**3.** Dans `items.json` : `{"id": "apple", "name": "Apple", "stackable": true, "max_stack": 20, "heal": 15}`.

C'est tout : le client envoie `{"type": "eat", "key": 0}`.

## Ce que le cœur vous donne

| Outil | Rôle |
|---|---|
| `@handler("type")` | Déclare la fonction d'un message. `@handler("type", out_of_world=True)` : accepté aussi dans le créateur de personnage |
| `session.send(message)` | Envoie un message au joueur |
| `session.error(texte, code)` | Envoie une erreur |
| `world.broadcast(session, message, include_self=False)` | À tous les joueurs de sa zone |
| `world.broadcast_all(message)` | À tout le serveur |
| `world.players`, `world.at(zone)`, `world.find(nom)` | Les joueurs connectés |
| `world.send_to(session, zone, position=None)` | Change un joueur de zone (portails, téléportation) |
| `world.on_join`, `world.on_leave` | Listes de fonctions `async f(session)` appelées à l'arrivée et au départ d'un joueur |
| `world.tasks` | Liste de fonctions `async f()` lancées en tâche de fond tant que le serveur tourne |
| `session.health`, `session.stamina` | Des `Gauge` : `add(n)`, `remove(n)`, `value`, `maximum`, `is_empty` |
| `session.progression` | `add_exp(n)` (renvoie les niveaux gagnés), `level`, `exp` |
| `await inventory.give(session, "stone", 12)` | Donne des objets ; renvoie ce qui n'a pas tenu |
| `await inventory.after_change(session)` | Après avoir changé l'inventaire à la main : sauvegarde et envoi |
| `await world_items.add(zone, ItemInstance("stone"), x, y, z)` | Pose un objet au sol (butin, récolte) |
| `storage.mark_dirty(session, "character")` | Sauvegarde bientôt (groupée) |
| `content.RULES`, `content.ITEMS` | Les règles de `game.json`, les objets de `items.json` (tous leurs champs) |
| `session.is_admin` | Pour les commandes réservées |
| `from common.log import log` | `log.info(...)`, `log.warning(...)` |

## Réagir à l'arrivée d'un joueur

```python
# server/modules/welcome_message.py
from server import world


async def greet(session):
    await session.send({"type": "chat", "channel": "global", "user_id": 0, "name": "Server",
                        "message": f"Welcome {session.name}!"})

world.on_join.append(greet)
```

## Une tâche de fond (respawn, météo, cycle jour / nuit)

```python
# server/modules/day_night.py
import asyncio

from server import world

DAY_LENGTH = 1200   # secondes


async def run():
    hour = 0
    while True:
        await asyncio.sleep(DAY_LENGTH / 24)
        hour = (hour + 1) % 24
        await world.broadcast_all({"type": "time_of_day", "hour": hour})

world.tasks.append(run)   # lancée au démarrage du serveur, arrêtée avec lui
```

## Sauvegarder vos propres données

**Une nouvelle colonne** (simple, pour une valeur par personnage) : une migration `migrations/002_gold.sql`, puis lisez-la et écrivez-la dans `server/storage.py` (`load_character` lit déjà toute la ligne ; ajoutez la colonne dans `save_character`).

**Une nouvelle table** (pour des données à part : quêtes, guildes, coffres de base) : une migration, puis des fonctions `async` dans votre module avec `db.pool()` :

```python
from common import db

async def load_quests(user_id: int) -> list:
    return await db.pool().fetch("SELECT quest_id, step FROM quests WHERE user_id = $1", user_id)
```

**Un inventaire qui n'est pas un joueur** (un coffre de base, une banque) : `storage.load_inventory("chest", uid)` et `storage.save_inventory("chest", uid, containers)` sont déjà génériques.

## Anti-triche sur les déplacements

Le serveur relaie les déplacements sans les vérifier. Pour un jeu compétitif, ajoutez un contrôle de vitesse dans `on_state` (`server/modules/movement.py`), juste après `state = read_state(data)` :

```python
MAX_SPEED = 12.0   # mètres par seconde, avec de la marge

elapsed = now - session.last_state_time
if session.position and elapsed < 1.0:
    distance = math.dist((state["x"], state["z"]), (session.position["x"], session.position["z"]))
    if distance > MAX_SPEED * elapsed:
        return   # ignoré : les autres voient toujours la dernière position valide
```

Pour aussi remettre le joueur en place chez lui, envoyez-lui un message à vous (par exemple `{"type": "correct_position", "position": session.position}`) que votre client applique.

## Les tests

`pytest` lance `tests/`. La logique (grilles, conteneurs, stats) se teste sans base de données : voir `tests/test_inventory.py`. `scripts/smoke_test.py` teste tout le trajet avec de vrais clients, sur une base de test.
