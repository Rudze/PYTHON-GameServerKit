# API HTTP

Adresse par défaut : `http://127.0.0.1:8000`. Une fois l'API lancée, la doc interactive (essayer chaque route dans le navigateur) est sur **`/docs`**.

- Corps des requêtes et des réponses en JSON (`Content-Type: application/json`).
- Les routes protégées veulent l'en-tête `Authorization: Bearer <token>` (le jeton de `/auth/login`).
- En cas d'erreur, la réponse est `{"detail": "message"}` ; une donnée invalide donne `422` avec `{"detail": [{"loc": [...], "msg": "..."}]}`.

| Méthode | Route | Jeton | Rôle |
|---|---|---|---|
| POST | `/auth/register` | non | Créer un compte |
| POST | `/auth/login` | non | Se connecter, recevoir un jeton |
| GET | `/auth/me` | oui | Le compte du jeton |
| GET | `/servers` | oui | Les serveurs de jeu en ligne et pas pleins |
| GET | `/servers/best` | oui | Le serveur le moins chargé |
| GET | `/health` | non | L'API et la base répondent-elles ? |

---

## POST /auth/register

Crée un compte. Limite : 5 par minute et par adresse.

| Champ | Règle |
|---|---|
| `username` | 3 à 20 lettres, chiffres ou `_` (unique, majuscules ignorées : `Bob` = `bob`) |
| `email` | Une adresse valide (unique) |
| `password` | 8 à 72 caractères |

```bash
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" \
  -d '{"username": "player_one", "email": "one@example.com", "password": "a long password"}'
```

| Code | Réponse |
|---|---|
| `201` | `{"id": 1, "username": "player_one", "is_admin": false}` |
| `409` | Nom ou email déjà pris |
| `422` | Champ invalide |
| `429` | Trop de requêtes |

## POST /auth/login

Limite : 10 par minute et par adresse.

```bash
curl -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" \
  -d '{"username": "player_one", "password": "a long password"}'
```

| Code | Réponse |
|---|---|
| `200` | `{"token": "eyJ...", "expires_in": 86400, "user": {"id": 1, "username": "player_one", "is_admin": false}}` |
| `401` | Mauvais nom ou mot de passe |
| `429` | Trop de requêtes |

Le jeton est valable `expires_in` secondes (`JWT_EXPIRE_SECONDS`). Il sert pour les routes protégées et pour se connecter au serveur de jeu.

## GET /auth/me

```bash
curl http://127.0.0.1:8000/auth/me -H "Authorization: Bearer eyJ..."
```

`200` : `{"id": 1, "username": "player_one", "is_admin": false}` ; `401` : jeton absent, faux ou expiré.

## GET /servers

Les serveurs de jeu en ligne (signe de vie depuis moins de 30 s) et pas pleins, le moins chargé en premier.

```json
[
  {"name": "main", "host": "127.0.0.1", "port": 5001, "region": "", "current_players": 12, "max_players": 100}
]
```

## GET /servers/best

Le premier de la liste : ce qu'il faut à un bouton « Jouer ». `503` si aucun serveur n'est disponible.

```json
{"name": "main", "host": "127.0.0.1", "port": 5001, "region": "", "current_players": 12, "max_players": 100}
```

## GET /health

`200` `{"status": "ok"}`, ou `503` `{"status": "database unreachable"}`. Pour Docker, un load balancer, la surveillance.

---

## Depuis Godot (GDScript)

Un petit client réutilisable, à mettre en autoload (par exemple `Api`) :

```gdscript
extends Node

const API_URL := "http://127.0.0.1:8000"

var token := ""


# ---
## Envoie une requête et attend la réponse : {"code": int, "body": Variant}.
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
		return {"code": 0, "body": null}   # serveur injoignable
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
## Le serveur le moins chargé : {"host", "port", ...}, ou {} si aucun.
func best_server() -> Dictionary:
	var response := await call_api(HTTPClient.METHOD_GET, "/servers/best")
	return response.body if response.code == 200 else {}
```

Utilisation :

```gdscript
if await Api.login("player_one", "a long password"):
	var server := await Api.best_server()
	Game.connect_to_server(server.host, server.port, Api.token)   # voir godot.md
```
