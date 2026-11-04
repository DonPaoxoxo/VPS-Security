from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import NoStoreCacheMiddleware
from app.routers import aapanel, agents, alerts, audit, auth, domains, overview, performance, reports, security_center, servers, settings
from ssc_core.config import get_settings

settings_ = get_settings()

# In production, the interactive API explorer (/docs, /redoc) and the raw
# schema (/openapi.json) are disabled — they cost nothing to an authenticated
# admin who already knows the routes, but freely hand an unauthenticated
# visitor the complete API surface (every route, every field name) for no
# operational benefit on a private, single-owner system. Still available in
# development.
_docs_enabled = settings_.environment != "production"

app = FastAPI(
    title="Server Security Center API",
    version="0.1.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Order matters: Starlette applies the LAST-added middleware outermost, so
# it runs FIRST on an incoming request and LAST on the outgoing response.
# RateLimitMiddleware reads request.client.host, so ProxyHeadersMiddleware
# (which rewrites scope["client"] from X-Forwarded-For) must be OUTER than
# it — added AFTER it — or the rate limiter would key every request off the
# reverse proxy's own address instead of the real client. TrustedHostMiddleware
# doesn't depend on that rewrite (it reads the Host header directly), so its
# relative position doesn't matter functionally. CORSMiddleware is added
# last (outermost of all) so its response-side headers still get applied
# even to a 429/403/400 raised by one of the inner layers.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings_.trusted_proxy_ips)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings_.trusted_hosts_list)
app.add_middleware(NoStoreCacheMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(servers.router)
app.include_router(agents.router)
app.include_router(aapanel.router)
app.include_router(domains.router)
app.include_router(overview.router)
app.include_router(security_center.router)
app.include_router(alerts.router)
app.include_router(settings.router)
app.include_router(performance.router)
app.include_router(audit.router)
app.include_router(reports.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
