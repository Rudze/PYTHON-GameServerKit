# Architecture

## Deux processus, une base

```
          HTTP (comptes, liste des serveurs)
 Client ─────────────────────────────────────► API  (python -m api, FastAPI, port 8000)
   │                                             │
   │   WebSocket (temps réel)                    │       ┌──────────────┐
   └─────────────────────────────────────► Serveur de jeu ─┤  PostgreSQL  │
                                         (python -m server,  └──────────────┘
                                          port 5001)          ▲
                                               └──────────────┘
```

| Processus | Rôle | Pourquoi séparé |
|---|---|---|
| **API** | Créer un compte, se connecter (donne un jeton), lister les serveurs de jeu | Requêtes courtes et sans état : on peut en lancer plusieurs derrière un load balancer |
| **Serveur de jeu** | Une connexion WebSocket par joueur : personnage, chat, déplacements, inventaire | Garde l'état des joueurs en mémoire ; on lance un serveur par monde / région |

Les deux lisent le même `JWT_SECRET` : le jeton donné par l'API à la connexion est vérifié par le serveur de jeu, sans requête à l'API.

Chaque serveur de jeu s'inscrit dans la table `servers` et donne son nombre de joueurs toutes les 10 secondes. L'API ne montre que les serveurs qui ont donné signe de vie depuis moins de 30 secondes : un serveur planté disparaît tout seul de la liste.

## Les dossiers

```
common/        Partagé par les deux processus
  config.py      Les réglages (.env)
  db.py          Le pool PostgreSQL (asyncpg) et les migrations
  tokens.py      Les jetons JWT
  log.py         Le logger
api/           L'API HTTP
  app.py         L'application FastAPI
  deps.py        "Qui fait la requête" (en-tête Authorization)
  ratelimit.py   La limite de requêtes par adresse
  routes/        auth.py, servers.py, health.py
server/        Le serveur de jeu
  main.py        Connexion, authentification, arrivée et départ d'un joueur
  session.py     Un joueur connecté
  router.py      Quel message va à quelle fonction (+ anti-flood)
  world.py       Qui est connecté, qui est où, qui voit qui
  storage.py     Lectures et écritures en base, sauvegardes groupées
  registry.py    L'inscription dans la liste des serveurs
  content.py     Les données du jeu (game.json, items.json)
  stats.py       Gauge (vie, endurance...) et Progression (niveau, exp)
  modules/       Le gameplay
    character.py   Nom, stats, apparence, créateur de personnage
    chat.py        Chat local et global
    movement.py    Déplacements, changement de zone
    inventory/     Grilles, sacs, coffres, équipement, objets au sol
data/          game.json et items.json : ce qui change d'un jeu à l'autre
migrations/    Le schéma SQL, fichier par fichier
scripts/       smoke_test.py (test de bout en bout)
tests/         Les tests unitaires (pytest)
```

## Le trajet d'un message

1. Le client envoie `{"type": "chat", "message": "salut"}` sur le WebSocket.
2. `server/main.py` le passe à `router.dispatch`.
3. Le routeur vérifie que c'est du JSON, que le joueur n'envoie pas trop de messages (30 par seconde en moyenne, 60 d'un coup), puis appelle la fonction déclarée avec `@handler("chat")` (dans `modules/chat.py`).
4. Le module fait son travail et répond avec `session.send(...)` ou `world.broadcast(...)`.
5. S'il a changé quelque chose à sauvegarder, il appelle `storage.mark_dirty(session, "character")` ou `"inventory"`.

## Pourquoi c'est rapide

| Choix | Effet |
|---|---|
| Tout est asynchrone (asyncio, asyncpg) | Un serveur gère des centaines de joueurs sur un seul cœur, rien ne bloque pendant une requête SQL |
| Sauvegardes groupées | Dix changements d'inventaire en une seconde = une seule écriture, `AUTOSAVE_DELAY` secondes plus tard |
| Positions sauvegardées toutes les 30 s | Pas une écriture à chaque pas ; sauvegarde immédiate à la déconnexion |
| JSONB pour les inventaires | Tout l'inventaire d'un joueur = une ligne, lue et écrite d'un coup |
| bcrypt dans un thread | La vérification d'un mot de passe (lente exprès) ne bloque pas les autres requêtes |
| Messages courts | Le client a `items.json` : le serveur n'envoie que l'id et ce qui est propre à l'objet |

## La sécurité

| Risque | Protection |
|---|---|
| Deviner un mot de passe | bcrypt, 10 connexions par minute et par adresse |
| Faux jeton | JWT signé (HS256) avec `JWT_SECRET`, durée limitée |
| Client qui inonde le serveur | 30 messages par seconde en moyenne, messages de 64 Ko maximum |
| Client qui triche sur l'inventaire | Le serveur décide de tout : place libre, taille, emplacement, objet dans lui-même, profondeur des sacs, distance des objets au sol |
| Deux connexions du même compte | La première est fermée et sauvegardée avant que la seconde ne charge |
| Valeurs folles (NaN, 1e300) | Les nombres de déplacement sont vérifiés et bornés |
