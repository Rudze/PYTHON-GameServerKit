"""A small limit on the account routes, per client address, against password guessing and spam:

    @router.post("/login", dependencies=[Depends(limit(10, 60))])   # 10 requests per minute

In memory: each API process counts on its own. Behind a proxy, run uvicorn with
--forwarded-allow-ips so that the client address is the real one."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


def limit(requests: int, seconds: float):
    hits: dict[str, deque] = defaultdict(deque)

    def check(request: Request):
        now = time.monotonic()
        address = request.client.host if request.client else "?"
        recent = hits[address]
        while recent and recent[0] <= now - seconds:
            recent.popleft()
        if len(recent) >= requests:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, try again later")
        recent.append(now)
        if len(hits) > 10_000:   # forget the addresses that went quiet
            for key in [key for key, value in hits.items() if not value or value[-1] <= now - seconds]:
                del hits[key]

    return check
