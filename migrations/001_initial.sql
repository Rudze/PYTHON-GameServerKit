-- The base schema. Applied once by common.db.migrate() (the API and the game server call it at
-- start). To change the schema later: add 002_....sql, never edit an applied file.

-- Accounts (the API creates them; the game server only reads them through the token)
CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT        NOT NULL,
    email         TEXT        NOT NULL,
    password_hash TEXT        NOT NULL,
    is_admin      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);
-- One account per name / email, whatever the case ("Bob" = "bob")
CREATE UNIQUE INDEX users_username_key ON users (lower(username));
CREATE UNIQUE INDEX users_email_key    ON users (lower(email));

-- Game servers: each one registers itself at start and reports every few seconds (heartbeat).
-- A server whose last heartbeat is old is offline (crashed or stopped).
CREATE TABLE servers (
    name            TEXT PRIMARY KEY,
    host            TEXT        NOT NULL,
    port            INTEGER     NOT NULL,
    region          TEXT        NOT NULL DEFAULT '',
    max_players     INTEGER     NOT NULL DEFAULT 100,
    current_players INTEGER     NOT NULL DEFAULT 0,
    last_heartbeat  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The character of each account: name, stats, look, and where they left the game
CREATE TABLE characters (
    user_id    BIGINT PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    name       TEXT        NOT NULL,
    level      INTEGER     NOT NULL DEFAULT 1,
    exp        INTEGER     NOT NULL DEFAULT 0,
    health     INTEGER     NOT NULL,
    stamina    INTEGER     NOT NULL,
    appearance JSONB       NOT NULL DEFAULT '{}',   -- {"hair": "short_01", "build": 0.5, ...}
    location   TEXT,                                -- the zone they were in (NULL: the default one)
    position   JSONB,                               -- {"x", "y", "z", "rot"} (NULL: the spawn)
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Inventories: all the containers of an owner in one row (a player: "pocket", the equipment
-- slots...; later a chest, a vehicle...). JSONB: {"pocket": {"rows", "cols", "slots": {...}}}
CREATE TABLE inventories (
    owner_type TEXT        NOT NULL,   -- "player", ...
    owner_id   TEXT        NOT NULL,   -- the user id as text, a chest uid...
    containers JSONB       NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_type, owner_id)
);

-- Items lying on the ground, with everything they contain
CREATE TABLE world_items (
    uid        TEXT PRIMARY KEY,
    location   TEXT             NOT NULL,
    x          DOUBLE PRECISION NOT NULL,
    y          DOUBLE PRECISION NOT NULL,
    z          DOUBLE PRECISION NOT NULL,
    rot        DOUBLE PRECISION NOT NULL DEFAULT 0,
    item       JSONB            NOT NULL,
    dropped_at TIMESTAMPTZ      NOT NULL DEFAULT now()
);
CREATE INDEX world_items_location ON world_items (location);
