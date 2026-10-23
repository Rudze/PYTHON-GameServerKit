# Game Server Kit

A reusable server base for multiplayer games: an **HTTP API** for accounts and the server list, and a **WebSocket game server** for everything in real time. Built with Python (FastAPI, websockets, asyncio) and PostgreSQL, made for Godot 4 clients but usable from any engine.

> 🇫🇷 Documentation en français : [doc/fr](doc/fr/README.md)

## Features

| | |
|---|---|
| **Accounts** | Register, log in (JWT), bcrypt passwords, request limits |
| **Server list** | Game servers register themselves and report their load; the API gives the least loaded one |
| **Real-time connection** | Token handshake, flood protection, one session per account, clean shutdown |
| **Character** | Name, health, stamina, level and exp, appearance, character creator |
| **Chat** | Local (zone) and global channels, length and rate limits |
| **Movement** | Configurable state fields relayed to the players of the same zone, zones / travel |
| **Inventory** | Grid inventory (sizes, rotation, stacks), equipment slots, bags, chests and belts nested in each other, items on the ground |
| **Data driven** | Rules in `data/game.json`, items in `data/items.json`: a new game = new data, same code |
| **Fast saves** | Asynchronous PostgreSQL, grouped writes, one JSONB row per inventory |

## Quick start

```bash
cp .env.example .env            # then set JWT_SECRET
docker compose up -d --build    # PostgreSQL + API (:8000) + game server (:5001)
curl http://127.0.0.1:8000/health
```

Without Docker for the kit itself (PostgreSQL still needed):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m api       # http://127.0.0.1:8000/docs
python -m server    # ws://127.0.0.1:5001
```

## How a client uses it

```
1. POST /auth/login             -> {"token": "..."}
2. GET  /servers/best           -> {"host": "...", "port": 5001}
3. connect ws://host:port, send {"type": "auth", "token": "..."}
4. receive welcome, stats, inventory, players around... then play
```

```json
{"type": "chat", "message": "hello", "channel": "local"}
{"type": "state", "location": "world", "x": 1.0, "y": 0.0, "z": 2.0, "rot": 1.57, "speed": 3.2, "vy": 0.0}
{"type": "move_item", "from_container": "pocket", "from": 0, "to_container": "back", "to": 0}
```

## Documentation

| | English | Français |
|---|---|---|
| Getting started | [doc/en/getting-started.md](doc/en/getting-started.md) | [doc/fr/getting-started.md](doc/fr/getting-started.md) |
| Architecture | [doc/en/architecture.md](doc/en/architecture.md) | [doc/fr/architecture.md](doc/fr/architecture.md) |
| HTTP API | [doc/en/http-api.md](doc/en/http-api.md) | [doc/fr/http-api.md](doc/fr/http-api.md) |
| WebSocket protocol | [doc/en/websocket.md](doc/en/websocket.md) | [doc/fr/websocket.md](doc/fr/websocket.md) |
| Godot integration | [doc/en/godot.md](doc/en/godot.md) | [doc/fr/godot.md](doc/fr/godot.md) |
| Configuration | [doc/en/configuration.md](doc/en/configuration.md) | [doc/fr/configuration.md](doc/fr/configuration.md) |
| Game data | [doc/en/game-data.md](doc/en/game-data.md) | [doc/fr/game-data.md](doc/fr/game-data.md) |
| Database | [doc/en/database.md](doc/en/database.md) | [doc/fr/database.md](doc/fr/database.md) |
| Extending | [doc/en/extending.md](doc/en/extending.md) | [doc/fr/extending.md](doc/fr/extending.md) |
| Deployment | [doc/en/deployment.md](doc/en/deployment.md) | [doc/fr/deployment.md](doc/fr/deployment.md) |

## Project layout

```
api/          HTTP API (FastAPI): auth, servers, health
server/       WebSocket game server: session, router, world, storage
  modules/    Gameplay: character, chat, movement, inventory
common/       Shared: settings, database pool and migrations, tokens, logging
data/         game.json and items.json (your game's rules and items)
migrations/   SQL schema, applied automatically at start
doc/          Documentation (en, fr)
tests/        Unit tests (pytest)
scripts/      End-to-end smoke test
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                          # logic, no database needed
python scripts/smoke_test.py    # end to end against a running API + server (test database)
```

## Requirements

Python 3.11+, PostgreSQL 14+.

## Versions

Releases are made by [semantic-release](https://semantic-release.gitbook.io) on every push to `main`, from the commit messages ([Conventional Commits](https://www.conventionalcommits.org)): `feat:` → minor version, `fix:` → patch, `feat!:` or `BREAKING CHANGE:` → major; `docs:`, `chore:`, `refactor:`, `test:` → no release. The bot updates `CHANGELOG.md` and `VERSION`, tags `vX.Y.Z` and publishes the GitHub release.
