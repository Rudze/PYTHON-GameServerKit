# Déploiement

## Docker Compose (un serveur)

```bash
cp .env.example .env
# Dans .env : JWT_SECRET (long et aléatoire), SERVER_PUBLIC_HOST (le domaine ou l'IP publique)
# Et le mot de passe de la base, dans l'environnement ou le .env : POSTGRES_PASSWORD=...
docker compose up -d --build
docker compose logs -f server
```

| Service | Port | Rôle |
|---|---|---|
| `postgres` | interne | La base (volume `postgres_data`) |
| `api` | 8000 | L'API HTTP |
| `server` | 5001 | Le serveur de jeu |

Mise à jour : `git pull && docker compose up -d --build`. Le serveur de jeu sauvegarde tous les joueurs avant de s'arrêter (`stop_grace_period: 30s`).

## Plusieurs serveurs de jeu

Chaque serveur de jeu est un processus `python -m server` avec son propre `SERVER_NAME` et `SERVER_PORT` (et `SERVER_PUBLIC_HOST` s'il est sur une autre machine), tous sur la **même base** et le **même `JWT_SECRET`**. Ils apparaissent dans `GET /servers`.

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

Un compte ne doit jouer que sur un serveur à la fois : les serveurs ne se parlent pas. Si votre jeu permet d'aller d'un serveur à l'autre, le client se déconnecte du premier (qui sauvegarde) avant de se connecter au second.

L'API, elle, peut être lancée plusieurs fois derrière un load balancer (la limite de requêtes est alors comptée par processus).

## En production

| Point | Comment |
|---|---|
| HTTPS / WSS | Mettez un reverse proxy (Caddy, Nginx, Traefik) devant : `https://` pour l'API, `wss://` pour le serveur de jeu. Le client Godot utilise alors `wss://` |
| Adresse réelle des clients | Derrière un proxy, lancez l'API avec `--forwarded-allow-ips` (uvicorn) pour que la limite de requêtes voie la vraie adresse |
| Secret | `JWT_SECRET` long et aléatoire ; le changer déconnecte tout le monde (les jetons deviennent invalides) |
| Base | Ne publiez pas le port 5432 ; sauvegardez régulièrement (`pg_dump`, voir [Base de données](database.md#sauvegarde)) |
| Logs | `LOG_LEVEL=INFO` ; `docker compose logs` |
| Santé | `GET /health` pour la surveillance |

Exemple Caddy :

```
api.mon-jeu.com {
    reverse_proxy api:8000
}
play.mon-jeu.com {
    reverse_proxy server:5001
}
```

## Sans Docker

Deux services systemd (ou ce que votre hébergeur propose) qui lancent, depuis le dossier du projet avec son `.venv` :

```
/chemin/du/projet/.venv/bin/python -m api
/chemin/du/projet/.venv/bin/python -m server
```

Le serveur de jeu s'arrête proprement sur `SIGTERM` (sauvegarde des joueurs, retrait de la liste des serveurs).
