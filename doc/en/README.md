# Documentation (English)

> Version française : [../fr/README.md](../fr/README.md)

Game Server Kit is a server base for multiplayer games: accounts, server list, real-time connection, character, chat, movement, grid inventory with bags and chests, items on the ground. It is reused from one game to the next by changing two data files, without touching the code.

| Page | Contents |
|---|---|
| [Getting started](getting-started.md) | Install, run, first test in 5 minutes |
| [Architecture](architecture.md) | The two processes, the folders, the path of a message |
| [HTTP API](http-api.md) | Every route, with curl and GDScript examples |
| [WebSocket protocol](websocket.md) | Every message of the game server, in JSON |
| [Godot integration](godot.md) | A complete Godot 4 client: connection, messages, inventory |
| [Configuration](configuration.md) | The `.env` variables |
| [Game data](game-data.md) | `game.json` (the rules) and `items.json` (the items) |
| [Database](database.md) | The PostgreSQL tables and the migrations |
| [Extending the kit](extending.md) | Adding a module, a message, a save, a hook |
| [Deployment](deployment.md) | Docker Compose, several servers, production |
