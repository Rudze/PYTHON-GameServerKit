# Documentation (français)

> English version: [../en/README.md](../en/README.md)

Game Server Kit est une base de serveur pour jeu multijoueur : comptes, liste des serveurs, connexion temps réel, personnage, chat, déplacements, inventaire en grille avec sacs et coffres, objets au sol. On le réutilise d'un jeu à l'autre en changeant deux fichiers de données, sans toucher au code.

| Page | Contenu |
|---|---|
| [Démarrage](getting-started.md) | Installer, lancer, faire un premier test en 5 minutes |
| [Architecture](architecture.md) | Les deux processus, les dossiers, le trajet d'un message |
| [API HTTP](http-api.md) | Toutes les routes, avec des exemples curl et GDScript |
| [Protocole WebSocket](websocket.md) | Tous les messages du serveur de jeu, en JSON |
| [Intégration Godot](godot.md) | Un client Godot 4 complet : connexion, messages, inventaire |
| [Configuration](configuration.md) | Les variables du fichier `.env` |
| [Données du jeu](game-data.md) | `game.json` (les règles) et `items.json` (les objets) |
| [Base de données](database.md) | Les tables PostgreSQL et les migrations |
| [Étendre le kit](extending.md) | Ajouter un module, un message, une sauvegarde, un hook |
| [Déploiement](deployment.md) | Docker Compose, plusieurs serveurs, production |
