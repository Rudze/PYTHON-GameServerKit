# Architecture

## Two processes, one database

```
          HTTP (accounts, server list)
 Client ─────────────────────────────────────► API  (python -m api, FastAPI, port 8000)
   │                                             │
   │   WebSocket (real time)                     │       ┌──────────────┐
   └─────────────────────────────────────► Game server ────┤  PostgreSQL  │
                                         (python -m server,  └──────────────┘
                                          port 5001)          ▲
                                               └──────────────┘
```

| Process | Role | Why separate |
|---|---|---|
| **API** | Create an account, log in (get a token), list the game servers | Short stateless requests: several can run behind a load balancer |
| **Game server** | One WebSocket connection per player: character, chat, movement, inventory | Keeps the players' state in memory; one server per world / region |

Both read the same `JWT_SECRET`: the token given by the API at login is checked by the game server, without asking the API.

Each game server registers itself in the `servers` table and reports its player count every 10 seconds. The API only lists the servers heard from in the last 30 seconds: a crashed server leaves the list on its own.

## The folders

```
common/        Shared by both processes
  config.py      The settings (.env)
  db.py          The PostgreSQL pool (asyncpg) and the migrations
  tokens.py      The JWT tokens
  log.py         The logger
api/           The HTTP API
  app.py         The FastAPI application
  deps.py        "Who sends the request" (Authorization header)
  ratelimit.py   The request limit per address
  routes/        auth.py, servers.py, health.py
server/        The game server
  main.py        Connection, authentication, a player arriving and leaving
  session.py     A connected player
  router.py      Which message goes to which function (+ flood protection)
  world.py       Who is connected, who is where, who sees whom
  storage.py     Database reads and writes, grouped saves
  registry.py    Registration in the server list
  content.py     The game data (game.json, items.json)
  stats.py       Gauge (health, stamina...) and Progression (level, exp)
  modules/       The gameplay
    character.py   Name, stats, appearance, character creator
    chat.py        Local and global chat
    movement.py    Movement, changing zone
    inventory/     Grids, bags, chests, equipment, items on the ground
data/          game.json and items.json: what changes from one game to the next
migrations/    The SQL schema, file by file
scripts/       smoke_test.py (end-to-end test)
tests/         The unit tests (pytest)
```

## The path of a message

1. The client sends `{"type": "chat", "message": "hi"}` on the WebSocket.
2. `server/main.py` hands it to `router.dispatch`.
3. The router checks it is JSON, that the player does not send too many messages (30 per second on average, 60 at once), then calls the function declared with `@handler("chat")` (in `modules/chat.py`).
4. The module does its work and answers with `session.send(...)` or `world.broadcast(...)`.
5. If it changed something to save, it calls `storage.mark_dirty(session, "character")` or `"inventory"`.

## Why it is fast

| Choice | Effect |
|---|---|
| Everything is asynchronous (asyncio, asyncpg) | One server handles hundreds of players on a single core, nothing blocks during an SQL query |
| Grouped saves | Ten inventory changes in one second = a single write, `AUTOSAVE_DELAY` seconds later |
| Positions saved every 30 s | Not one write per step; saved at once on disconnection |
| JSONB for inventories | A player's whole inventory = one row, read and written at once |
| bcrypt in a thread | Checking a password (slow on purpose) does not block the other requests |
| Short messages | The client has `items.json`: the server only sends the id and what is specific to the item |

## Security

| Risk | Protection |
|---|---|
| Password guessing | bcrypt, 10 logins per minute per address |
| Fake token | JWT signed (HS256) with `JWT_SECRET`, limited lifetime |
| Client flooding the server | 30 messages per second on average, 64 KB messages at most |
| Client cheating on the inventory | The server decides everything: free room, size, slot, item inside itself, bag depth, distance to ground items |
| Two connections of one account | The first is closed and saved before the second loads |
| Crazy values (NaN, 1e300) | Movement numbers are checked and clamped |
