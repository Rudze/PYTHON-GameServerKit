# Base de données

PostgreSQL, par le pilote asynchrone asyncpg. Les colonnes JSONB arrivent dans Python en `dict` / `list` directement.

## Les tables

| Table | Clé | Contenu |
|---|---|---|
| `users` | `id` | Les comptes : `username`, `email` (uniques, majuscules ignorées), `password_hash` (bcrypt), `is_admin`, `created_at`, `last_login_at` |
| `servers` | `name` | Les serveurs de jeu : `host`, `port`, `region`, `max_players`, `current_players`, `last_heartbeat` |
| `characters` | `user_id` | Le personnage d'un compte : `name`, `level`, `exp`, `health`, `stamina`, `appearance` (JSONB), `location`, `position` (JSONB), `updated_at` |
| `inventories` | `owner_type`, `owner_id` | Tous les conteneurs d'un propriétaire en une ligne JSONB (`"player"` + id du compte ; à vous d'ajouter `"chest"`, `"guild"`...) |
| `world_items` | `uid` | Les objets au sol : `location`, `x`, `y`, `z`, `rot`, `item` (JSONB, avec son contenu), `dropped_at` |
| `schema_migrations` | `name` | Les migrations déjà appliquées |

Supprimer un compte supprime son personnage (`ON DELETE CASCADE`). Son inventaire est à supprimer à part (`owner_type = 'player' AND owner_id = '<id>'`).

### Le format d'un inventaire

```json
{
  "pocket": {"slots": {"0": {"uid": "1bd9...", "item_id": "stone", "data": {"quantity": 15}}}},
  "back":   {"slots": {"0": {"uid": "9865...", "item_id": "small_backpack", "data": {},
                             "container": {"slots": {"3": {"uid": "...", "item_id": "health_potion", "data": {"quantity": 2}}}}}}}
}
```

Seuls les conteneurs non vides sont écrits. La taille de la poche vient de `game.json` : si elle rétrécit, les objets qui ne tiennent plus sont rangés ailleurs au chargement.

## Les migrations

Le schéma est dans `migrations/*.sql`. Au démarrage, l'API et le serveur de jeu appliquent les fichiers pas encore appliqués, par ordre de nom, chacun dans une transaction (un verrou évite que deux processus le fassent en même temps).

Pour changer le schéma : **ajoutez** un fichier, ne modifiez jamais un fichier déjà appliqué.

```sql
-- migrations/002_gold.sql
ALTER TABLE characters ADD COLUMN gold INTEGER NOT NULL DEFAULT 0;
```

## Requêtes utiles

```sql
-- Donner les droits admin
UPDATE users SET is_admin = TRUE WHERE lower(username) = 'player_one';

-- Les serveurs en ligne
SELECT name, host, port, current_players FROM servers WHERE last_heartbeat > now() - interval '30 seconds';

-- Ce qu'un joueur a dans sa poche
SELECT jsonb_pretty(containers -> 'pocket') FROM inventories WHERE owner_type = 'player' AND owner_id = '1';

-- Les objets au sol d'une zone
SELECT uid, item ->> 'item_id', x, y, z FROM world_items WHERE location = 'world';
```

Les droits admin sont dans le jeton : le joueur doit se reconnecter (nouveau `login`) pour les avoir. Dans le code serveur : `session.is_admin`.

## Sauvegarde

```bash
docker compose exec postgres pg_dump -U game game > backup.sql      # sauvegarder
docker compose exec -T postgres psql -U game game < backup.sql      # restaurer
```
