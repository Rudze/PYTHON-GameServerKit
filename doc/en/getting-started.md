# Getting started

## Requirements

| Tool | Version | Why |
|---|---|---|
| Python | 3.11 or later | The API and the game server |
| PostgreSQL | 14 or later | The database (Docker is enough) |
| Docker | any | Optional: run PostgreSQL, or the whole kit at once |

## Option A: everything with Docker (simplest)

```bash
cp .env.example .env          # then change JWT_SECRET
docker compose up -d --build
```

This starts PostgreSQL, the API on port 8000 and a game server on port 5001. Check:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

## Option B: locally (for development)

**1. PostgreSQL.** Quickest, with Docker:

```bash
docker run -d --name game-postgres -e POSTGRES_USER=game -e POSTGRES_PASSWORD=change-me \
  -e POSTGRES_DB=game -p 5432:5432 postgres:17-alpine
```

**2. Python.**

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then change JWT_SECRET
```

**3. Run both processes** (two terminals, from the project root):

```bash
python -m api       # HTTP API    -> http://127.0.0.1:8000  (interactive docs: /docs)
python -m server    # game server -> ws://127.0.0.1:5001
```

The database schema is created on the first run (`migrations/` folder).

## First test

Create an account, log in, pick a server:

```bash
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" \
  -d '{"username": "player_one", "email": "one@example.com", "password": "a long password"}'

curl -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" \
  -d '{"username": "player_one", "password": "a long password"}'
# {"token": "eyJ...", "expires_in": 86400, "user": {...}}

curl http://127.0.0.1:8000/servers/best -H "Authorization: Bearer eyJ..."
# {"name": "main", "host": "127.0.0.1", "port": 5001, ...}
```

Then the full end-to-end test (two fake players: chat, movement, inventory, items on the ground):

```bash
pip install -r requirements-dev.txt
python scripts/smoke_test.py       # Run it on a test database: it creates accounts
pytest                             # The logic tests (no database needed)
```

## Next

- Adapt the rules and items to your game: [Game data](game-data.md)
- Plug in your Godot client: [Godot integration](godot.md)
- Add your gameplay: [Extending the kit](extending.md)
