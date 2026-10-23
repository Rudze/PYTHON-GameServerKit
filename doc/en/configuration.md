# Configuration

Settings are read from environment variables, or from a `.env` file at the project root (copy `.env.example`). A variable already in the environment wins over the `.env`. Never commit the `.env`.

## Shared (API and game server)

| Variable | Default | Role |
|---|---|---|
| `DATABASE_URL` | **required** | `postgresql://user:password@host:5432/database` |
| `DB_POOL_MIN` | `2` | PostgreSQL connections kept open per process |
| `DB_POOL_MAX` | `10` | Connections at most per process |
| `JWT_SECRET` | **required** | Token signing key, the same for the API and every game server. Long and random: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_EXPIRE_SECONDS` | `86400` | Token lifetime (24 h) |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

## API

| Variable | Default | Role |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Listen address |
| `API_PORT` | `8000` | Port |

## Game server

| Variable | Default | Role |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Listen address |
| `SERVER_PORT` | `5001` | Port |
| `SERVER_NAME` | `main` | Name in the server list, **unique** per game server |
| `SERVER_PUBLIC_HOST` | `127.0.0.1` | The address clients use to reach it (domain or public IP in production) |
| `SERVER_MAX_PLAYERS` | `100` | Above it, connections are refused (`server_full`) |
| `DATA_DIR` | `./data` | The folder of `game.json` and `items.json` |
| `REQUIRE_CONTENT_HASH` | `false` | `true`: refuse clients whose game data differs (`content_mismatch`) |
| `AUTOSAVE_DELAY` | `2.0` | Seconds between a change and its save; the changes in between are saved together |

## Settings in the code

Rarely changed, at the top of their file:

| Constant | File | Default | Role |
|---|---|---|---|
| `MESSAGES_PER_SECOND`, `BURST` | `server/router.py` | `30`, `60` | Flood protection per player |
| `MAX_MESSAGE_SIZE` | `server/main.py` | 64 KB | Largest message |
| `AUTH_TIMEOUT` | `server/main.py` | `10` s | Time to send `auth` |
| `POSITION_SAVE_INTERVAL` | `server/storage.py` | `30` s | How often positions are saved |
| `HEARTBEAT` | `server/registry.py` | `10` s | How often a server reports |
| `HEARTBEAT_TIMEOUT` | `api/routes/servers.py` | `30` s | Silence after which a server is offline |
| `MAX_DEPTH` | `server/modules/inventory/containers.py` | `16` | Bags in bags, at most |
