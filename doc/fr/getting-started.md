# Démarrage

## Ce qu'il faut

| Outil | Version | Pourquoi |
|---|---|---|
| Python | 3.11 ou plus | L'API et le serveur de jeu |
| PostgreSQL | 14 ou plus | La base de données (Docker suffit) |
| Docker | n'importe laquelle | Optionnel : lancer PostgreSQL, ou tout le kit d'un coup |

## Option A : tout avec Docker (le plus simple)

```bash
cp .env.example .env          # puis changez JWT_SECRET
docker compose up -d --build
```

Ça lance PostgreSQL, l'API sur le port 8000 et un serveur de jeu sur le port 5001. Vérification :

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

## Option B : en local (pour développer)

**1. PostgreSQL.** Le plus rapide, avec Docker :

```bash
docker run -d --name game-postgres -e POSTGRES_USER=game -e POSTGRES_PASSWORD=change-me \
  -e POSTGRES_DB=game -p 5432:5432 postgres:17-alpine
```

**2. Python.**

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # puis changez JWT_SECRET
```

**3. Lancer les deux processus** (deux terminaux, depuis la racine du projet) :

```bash
python -m api       # API HTTP     -> http://127.0.0.1:8000  (doc interactive : /docs)
python -m server    # serveur de jeu -> ws://127.0.0.1:5001
```

Le schéma de la base est créé tout seul au premier lancement (dossier `migrations/`).

## Premier test

Créer un compte, se connecter, choisir un serveur :

```bash
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" \
  -d '{"username": "player_one", "email": "one@example.com", "password": "a long password"}'

curl -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" \
  -d '{"username": "player_one", "password": "a long password"}'
# {"token": "eyJ...", "expires_in": 86400, "user": {...}}

curl http://127.0.0.1:8000/servers/best -H "Authorization: Bearer eyJ..."
# {"name": "main", "host": "127.0.0.1", "port": 5001, ...}
```

Puis le test complet de bout en bout (deux faux joueurs : chat, déplacement, inventaire, objets au sol) :

```bash
pip install -r requirements-dev.txt
python scripts/smoke_test.py       # À lancer sur une base de test : il crée des comptes
pytest                             # Les tests de la logique (sans base de données)
```

## Ensuite

- Adapter les règles et les objets à votre jeu : [Données du jeu](game-data.md)
- Brancher votre client Godot : [Intégration Godot](godot.md)
- Ajouter votre gameplay : [Étendre le kit](extending.md)
