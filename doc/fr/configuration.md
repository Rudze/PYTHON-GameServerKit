# Configuration

Les réglages sont lus dans les variables d'environnement, ou dans un fichier `.env` à la racine du projet (copiez `.env.example`). Une variable déjà dans l'environnement passe avant le `.env`. Ne commitez jamais le `.env`.

## Communs (API et serveur de jeu)

| Variable | Défaut | Rôle |
|---|---|---|
| `DATABASE_URL` | **obligatoire** | `postgresql://utilisateur:mot_de_passe@hôte:5432/base` |
| `DB_POOL_MIN` | `2` | Connexions PostgreSQL ouvertes en permanence par processus |
| `DB_POOL_MAX` | `10` | Connexions au plus par processus |
| `JWT_SECRET` | **obligatoire** | Clé de signature des jetons, la même pour l'API et tous les serveurs de jeu. Longue et aléatoire : `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_EXPIRE_SECONDS` | `86400` | Durée de validité d'un jeton (24 h) |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` ou `ERROR` |

## API

| Variable | Défaut | Rôle |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Adresse d'écoute |
| `API_PORT` | `8000` | Port |

## Serveur de jeu

| Variable | Défaut | Rôle |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Adresse d'écoute |
| `SERVER_PORT` | `5001` | Port |
| `SERVER_NAME` | `main` | Nom dans la liste des serveurs, **unique** par serveur de jeu |
| `SERVER_PUBLIC_HOST` | `127.0.0.1` | L'adresse que les clients utilisent pour le joindre (domaine ou IP publique en production) |
| `SERVER_MAX_PLAYERS` | `100` | Au-delà, les connexions sont refusées (`server_full`) |
| `DATA_DIR` | `./data` | Le dossier de `game.json` et `items.json` |
| `REQUIRE_CONTENT_HASH` | `false` | `true` : refuse les clients dont les données du jeu diffèrent (`content_mismatch`) |
| `AUTOSAVE_DELAY` | `2.0` | Secondes entre un changement et sa sauvegarde ; les changements entre-temps sont sauvegardés ensemble |

## Réglages dans le code

Rarement à changer, en haut de leur fichier :

| Constante | Fichier | Défaut | Rôle |
|---|---|---|---|
| `MESSAGES_PER_SECOND`, `BURST` | `server/router.py` | `30`, `60` | Anti-flood par joueur |
| `MAX_MESSAGE_SIZE` | `server/main.py` | 64 Ko | Taille maximale d'un message |
| `AUTH_TIMEOUT` | `server/main.py` | `10` s | Délai pour envoyer `auth` |
| `POSITION_SAVE_INTERVAL` | `server/storage.py` | `30` s | Fréquence de sauvegarde des positions |
| `HEARTBEAT` | `server/registry.py` | `10` s | Fréquence du signe de vie |
| `HEARTBEAT_TIMEOUT` | `api/routes/servers.py` | `30` s | Silence après lequel un serveur est hors ligne |
| `MAX_DEPTH` | `server/modules/inventory/containers.py` | `16` | Sacs dans des sacs, au plus |
