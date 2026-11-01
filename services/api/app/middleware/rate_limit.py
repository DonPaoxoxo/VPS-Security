"""In-memory sliding-window rate limiting.

This is intentionally simple: a single-process in-memory counter, adequate
for a single-instance deployment on one VPS (the deployment this platform is
built for). It is NOT shared across multiple API replicas — if this is ever
scaled horizontally, replace the store with Redis (the limiter interface
below would stay the same)."""

import time
from collections import defaultdict

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# path-prefix -> (max requests, window seconds). Checked in order; first
# match wins. Falls back to a generous default for everything else so normal
# dashboard usage is never throttled.
_RULES: list[tuple[str, int, int]] = [
    ("/auth/login", 10, 60),
    ("/auth/setup", 5, 60),
    ("/agents/enroll", 10, 60),
    ("/", 300, 60),  # default: everything else, per IP
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[tuple[str, str], list[float]] = defaultdict(list)

    def _rule_for(self, path: str) -> tuple[str, int, int]:
        for prefix, limit, window in _RULES[:-1]:
            if path.startswith(prefix):
                return prefix, limit, window
        return _RULES[-1]

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        prefix, limit, window = self._rule_for(request.url.path)
        key = (client_ip, prefix)

        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - window
        while hits and hits[0] < cutoff:
            hits.pop(0)
        if not hits:
            # Avoid leaking memory for IPs that only ever send a few requests.
            del self._hits[key]
            hits = self._hits[key]

        if len(hits) >= limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests — please slow down."},
                headers={"Retry-After": str(window)},
            )

        hits.append(now)
        return await call_next(request)
