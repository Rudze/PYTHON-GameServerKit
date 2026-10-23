# Deployment

## Docker Compose (one server)

```bash
cp .env.example .env
# In .env: JWT_SECRET (long and random), SERVER_PUBLIC_HOST (the domain or public IP)
# And the database password, in the environment or the .env: POSTGRES_PASSWORD=...
docker compose up -d --build
docker compose logs -f server
```

| Service | Port | Role |
|---|---|---|
| `postgres` | internal | The database (volume `postgres_data`) |
| `api` | 8000 | The HTTP API |
| `server` | 5001 | The game server |

Update: `git pull && docker compose up -d --build`. The game server saves every player before stopping (`stop_grace_period: 30s`).

## Several game servers

Each game server is a `python -m server` process with its own `SERVER_NAME` and `SERVER_PORT` (and `SERVER_PUBLIC_HOST` if it is on another machine), all on the **same database** and the **same `JWT_SECRET`**. They show up in `GET /servers`.

```yaml
  server_eu_2:
    build: .
    command: python -m server
    env_file: .env
    environment:
      DATABASE_URL: postgresql://game:${POSTGRES_PASSWORD:-change-me}@postgres:5432/game
      SERVER_NAME: eu-2
      SERVER_PORT: 5002
    ports:
      - "5002:5002"
```

An account should play on one server at a time: the servers do not talk to each other. If your game lets players go from one server to another, the client disconnects from the first one (which saves) before connecting to the second.

The API can run several times behind a load balancer (the request limit is then counted per process).

## In production

| Point | How |
|---|---|
| HTTPS / WSS | Put a reverse proxy (Caddy, Nginx, Traefik) in front: `https://` for the API, `wss://` for the game server. The Godot client then uses `wss://` |
| Real client address | Behind a proxy, run the API with `--forwarded-allow-ips` (uvicorn) so the request limit sees the real address |
| Secret | `JWT_SECRET` long and random; changing it logs everyone out (tokens become invalid) |
| Database | Do not publish port 5432; back up regularly (`pg_dump`, see [Database](database.md#backup)) |
| Logs | `LOG_LEVEL=INFO`; `docker compose logs` |
| Health | `GET /health` for monitoring |

Caddy example:

```
api.my-game.com {
    reverse_proxy api:8000
}
play.my-game.com {
    reverse_proxy server:5001
}
```

## Without Docker

Two systemd services (or whatever your host offers) running, from the project folder with its `.venv`:

```
/path/to/project/.venv/bin/python -m api
/path/to/project/.venv/bin/python -m server
```

The game server stops cleanly on `SIGTERM` (players saved, removed from the server list).
