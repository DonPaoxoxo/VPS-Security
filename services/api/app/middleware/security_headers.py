"""Response headers that apply to every endpoint in this API, regardless of
auth state: this is a private dashboard's backend, not a public content API,
so nothing it returns should ever be cached by a browser, a shared/corporate
proxy, or a CDN placed in front of it later."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class NoStoreCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        return response
