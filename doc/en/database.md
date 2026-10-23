# Database

PostgreSQL, through the asynchronous asyncpg driver. JSONB columns come into Python as `dict` / `list` directly.

## The tables

| Table | Key | Contents |
|---|---|---|
| `users` | `id` | Accounts: `username`, `email` (unique, case ignored), `password_hash` (bcrypt), `is_admin`, `created_at`, `last_login_at` |
| `servers` | `name` | Game servers: `host`, `port`, `region`, `max_players`, `current_players`, `last_heartbeat` |
| `characters` | `user_id` | An account's character: `name`, `level`, `exp`, `health`, `stamina`, `appearance` (JSONB), `location`, `position` (JSONB), `updated_at` |
| `inventories` | `owner_type`, `owner_id` | All the containers of an owner in one JSONB row (`"player"` + account id; add `"chest"`, `"guild"`... yourself) |
| `world_items` | `uid` | Items on the ground: `location`, `x`, `y`, `z`, `rot`, `item` (JSONB, with its contents), `dropped_at` |
| `schema_migrations` | `name` | The migrations already applied |

Deleting an account deletes its character (`ON DELETE CASCADE`). Its inventory is deleted separately (`owner_type = 'player' AND owner_id = '<id>'`).

### The inventory format

```json
{
  "pocket": {"slots": {"0": {"uid": "1bd9...", "item_id": "stone", "data": {"quantity": 15}}}},
  "back":   {"slots": {"0": {"uid": "9865...", "item_id": "small_backpack", "data": {},
                             "container": {"slots": {"3": {"uid": "...", "item_id": "health_potion", "data": {"quantity": 2}}}}}}}
}
```

Only non-empty containers are written. The pocket size comes from `game.json`: if it shrinks, the items that no longer fit are put elsewhere when loading.

## Migrations

The schema is in `migrations/*.sql`. At start, the API and the game server apply the files not applied yet, in name order, each in a transaction (a lock keeps two processes from doing it at once).

To change the schema: **add** a file, never edit a file already applied.

```sql
-- migrations/002_gold.sql
ALTER TABLE characters ADD COLUMN gold INTEGER NOT NULL DEFAULT 0;
```

## Useful queries

```sql
-- Grant admin rights
UPDATE users SET is_admin = TRUE WHERE lower(username) = 'player_one';

-- Online servers
SELECT name, host, port, current_players FROM servers WHERE last_heartbeat > now() - interval '30 seconds';

-- What a player has in their pocket
SELECT jsonb_pretty(containers -> 'pocket') FROM inventories WHERE owner_type = 'player' AND owner_id = '1';

-- The items on the ground of a zone
SELECT uid, item ->> 'item_id', x, y, z FROM world_items WHERE location = 'world';
```

Admin rights are in the token: the player must log in again to get them. In server code: `session.is_admin`.

## Backup

```bash
docker compose exec postgres pg_dump -U game game > backup.sql      # back up
docker compose exec -T postgres psql -U game game < backup.sql      # restore
```
