# HTTP API

Default address: `http://127.0.0.1:8000`. Once the API runs, the interactive documentation (try every route in the browser) is at **`/docs`**.

- Request and response bodies are JSON (`Content-Type: application/json`).
- Protected routes need the `Authorization: Bearer <token>` header (the token from `/auth/login`).
- On error the response is `{"detail": "message"}`; invalid data gives `422` with `{"detail": [{"loc": [...], "msg": "..."}]}`.

| Method | Route | Token | Role |
|---|---|---|---|
| POST | `/auth/register` | no | Create an account |
| POST | `/auth/login` | no | Log in, get a token |
| GET | `/auth/me` | yes | The token's account |
| GET | `/servers` | yes | The game servers online and not full |
| GET | `/servers/best` | yes | The least loaded server |
| GET | `/health` | no | Are the API and the database up? |

---

## POST /auth/register

Creates an account. Limit: 5 per minute per address.

| Field | Rule |
|---|---|
| `username` | 3 to 20 letters, digits or `_` (unique, case ignored: `Bob` = `bob`) |
| `email` | A valid address (unique) |
| `password` | 8 to 72 characters |

```bash
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" \
  -d '{"username": "player_one", "email": "one@example.com", "password": "a long password"}'
```

| Code | Response |
|---|---|
| `201` | `{"id": 1, "username": "player_one", "is_admin": false}` |
| `409` | Username or email already used |
| `422` | Invalid field |
| `429` | Too many requests |

## POST /auth/login

Limit: 10 per minute per address.

```bash
curl -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" \
  -d '{"username": "player_one", "password": "a long password"}'
```

| Code | Response |
|---|---|
| `200` | `{"token": "eyJ...", "expires_in": 86400, "user": {"id": 1, "username": "player_one", "is_admin": false}}` |
| `401` | Wrong username or password |
| `429` | Too many requests |

The token is valid for `expires_in` seconds (`JWT_EXPIRE_SECONDS`). It is used for the protected routes and to connect to the game server.

## GET /auth/me

```bash
curl http://127.0.0.1:8000/auth/me -H "Authorization: Bearer eyJ..."
```

`200`: `{"id": 1, "username": "player_one", "is_admin": false}`; `401`: token missing, wrong or expired.

## GET /servers

The game servers online (heard from in the last 30 s) and not full, the least loaded first.

```json
[
  {"name": "main", "host": "127.0.0.1", "port": 5001, "region": "", "current_players": 12, "max_players": 100}
]
```

## GET /servers/best

The first of the list: what a "Play" button needs. `503` if no server is available.

```json
{"name": "main", "host": "127.0.0.1", "port": 5001, "region": "", "current_players": 12, "max_players": 100}
```

## GET /health

`200` `{"status": "ok"}`, or `503` `{"status": "database unreachable"}`. For Docker, a load balancer, monitoring.

---

## From Godot (GDScript)

A small reusable client, to set as an autoload (for example `Api`):

```gdscript
extends Node

const API_URL := "http://127.0.0.1:8000"

var token := ""


# ---
## Sends a request and waits for the answer: {"code": int, "body": Variant}.
func call_api(method: HTTPClient.Method, route: String, body = null) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)
	var headers := ["Content-Type: application/json"]
	if token != "":
		headers.append("Authorization: Bearer " + token)
	var data := "" if body == null else JSON.stringify(body)
	http.request(API_URL + route, headers, method, data)
	var result: Array = await http.request_completed   # [result, code, headers, body]
	http.queue_free()
	if result[0] != HTTPRequest.RESULT_SUCCESS:
		return {"code": 0, "body": null}   # server unreachable
	return {"code": result[1], "body": JSON.parse_string(result[3].get_string_from_utf8())}


# ---
func register(username: String, email: String, password: String) -> Dictionary:
	return await call_api(HTTPClient.METHOD_POST, "/auth/register",
		{"username": username, "email": email, "password": password})


# ---
func login(username: String, password: String) -> bool:
	var response := await call_api(HTTPClient.METHOD_POST, "/auth/login",
		{"username": username, "password": password})
	if response.code != 200:
		return false
	token = response.body.token
	return true


# ---
## The least loaded server: {"host", "port", ...}, or {} if none.
func best_server() -> Dictionary:
	var response := await call_api(HTTPClient.METHOD_GET, "/servers/best")
	return response.body if response.code == 200 else {}
```

Usage:

```gdscript
if await Api.login("player_one", "a long password"):
	var server := await Api.best_server()
	Game.connect_to_server(server.host, server.port, Api.token)   # see godot.md
```
