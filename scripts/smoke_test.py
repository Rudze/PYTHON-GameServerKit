"""End to end check of a running API + game server, as two real clients would use them.

    python scripts/smoke_test.py [api_url] [ws_url]
    (defaults: http://127.0.0.1:8000  ws://127.0.0.1:5001)

Creates two throwaway accounts, logs them in, connects both to the game server, then checks:
chat, movement relay, inventory moves, dropping and picking up an item. Needs DATABASE_URL (it
puts a few items in the first player's inventory to have something to move).
Use it on a test database, not in production."""
import asyncio
import json
import os
import secrets
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402
import websockets  # noqa: E402

from common.config import settings  # noqa: E402

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
WS = sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:5001"


def http(method: str, path: str, body: dict | None = None, token: str = "") -> tuple[int, dict]:
    request = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


class Client:
    def __init__(self, token: str):
        self.token = token
        self.socket = None

    async def connect(self):
        self.socket = await websockets.connect(WS)
        await self.send({"type": "auth", "token": self.token})
        return await self.expect("welcome")

    async def send(self, message: dict):
        await self.socket.send(json.dumps(message))

    async def expect(self, message_type: str, timeout: float = 3.0) -> dict:
        """Reads messages until one of `message_type` (an "error" first fails the check)."""
        async def wait():
            while True:
                message = json.loads(await self.socket.recv())
                if message["type"] == message_type:
                    return message
                if message["type"] == "error":
                    raise AssertionError(f"Expected {message_type}, got error {message}")
        return await asyncio.wait_for(wait(), timeout)


def check(condition: bool, label: str):
    print(("  ok   " if condition else "  FAIL ") + label)
    if not condition:
        sys.exit(1)


async def main():
    suffix = secrets.token_hex(3)
    accounts = []
    for name in ("alice", "bob"):
        username = f"{name}_{suffix}"
        status, _ = http("POST", "/auth/register", {"username": username, "email": f"{username}@test.local",
                                                    "password": "password123"})
        check(status == 201, f"register {username}")
        status, login = http("POST", "/auth/login", {"username": username, "password": "password123"})
        check(status == 200 and login["token"], f"login {username}")
        accounts.append(login)
    check(http("POST", "/auth/login", {"username": accounts[0]["user"]["username"], "password": "wrong"})[0] == 401,
          "wrong password refused")
    check(http("GET", "/auth/me", token=accounts[0]["token"])[1]["username"] == accounts[0]["user"]["username"],
          "GET /auth/me")
    status, best = http("GET", "/servers/best", token=accounts[0]["token"])
    check(status == 200 and best["port"], f"GET /servers/best -> {best.get('name')} {best.get('host')}:{best.get('port')}")

    # Something to move: a backpack (worn) and stones in the pocket of the first player
    connection = await asyncpg.connect(settings().database_url)
    containers = {"pocket": {"slots": {"0": {"uid": secrets.token_hex(16), "item_id": "stone", "data": {"quantity": 30}}}},
                  "back": {"slots": {"0": {"uid": secrets.token_hex(16), "item_id": "small_backpack", "data": {}}}}}
    await connection.execute("INSERT INTO inventories (owner_type, owner_id, containers) VALUES ('player', $1, $2)",
                             str(accounts[0]["user"]["id"]), json.dumps(containers))
    await connection.close()

    alice, bob = Client(accounts[0]["token"]), Client(accounts[1]["token"])
    welcome = await alice.connect()
    check(welcome["location"] == "world", "alice welcome")
    inventory = await alice.expect("inventory")
    check(inventory["containers"]["pocket"]["items"]["0"]["quantity"] == 30, "alice inventory loaded")
    await bob.connect()
    joined = await alice.expect("player_joined")
    check(joined["user_id"] == accounts[1]["user"]["id"], "alice sees bob join")

    await alice.send({"type": "chat", "message": "  hello   bob "})
    chat = await bob.expect("chat")
    check(chat["message"] == "hello bob", "chat relayed")

    await bob.send({"type": "state", "location": "world", "x": 1, "y": 0, "z": 2, "rot": 0, "speed": 3, "vy": 0})
    state = await alice.expect("player_state")
    check(state["state"]["x"] == 1.0, "movement relayed")

    bag_uid = inventory["containers"]["back"]["items"]["0"]["uid"]
    await alice.send({"type": "move_item", "from_container": "pocket", "from": 0, "to_container": "pocket",
                      "to": 5, "split": True})
    inventory = await alice.expect("inventory")
    check(sorted(i["quantity"] for i in inventory["containers"]["pocket"]["items"].values()) == [15, 15], "split stack")
    await alice.send({"type": "move_item", "from_container": "pocket", "from": 5, "to_container": bag_uid, "to": 0})
    await alice.expect("inventory")
    await alice.send({"type": "open_container", "uid": bag_uid})
    bag = await alice.expect("container")
    check(bag["items"]["0"]["quantity"] == 15, "stones moved into the backpack")

    await alice.send({"type": "drop_item", "from_container": "pocket", "from": 0, "x": 0, "y": 0, "z": 0})
    dropped = await bob.expect("world_item_added")
    check(dropped["item"]["item_id"] == "stone", "bob sees the dropped stones")
    await bob.send({"type": "pick_up", "uid": dropped["item"]["uid"]})
    inventory = await bob.expect("inventory")
    check(inventory["containers"]["pocket"]["items"]["0"]["quantity"] == 15, "bob picked them up")

    await bob.socket.close()
    left = await alice.expect("player_left")
    check(left["user_id"] == accounts[1]["user"]["id"], "alice sees bob leave")
    await alice.socket.close()
    print("All checks passed")


if __name__ == "__main__":
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    asyncio.run(main())
