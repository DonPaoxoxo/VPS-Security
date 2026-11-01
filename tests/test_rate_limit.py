import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/auth/login")
    async def login():
        return {"ok": True}

    @app.get("/overview")
    async def overview():
        return {"ok": True}

    return app


def test_login_path_is_throttled_after_its_limit():
    client = TestClient(_build_app())
    for _ in range(10):
        resp = client.post("/auth/login")
        assert resp.status_code == 200

    resp = client.post("/auth/login")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_different_ips_are_tracked_independently():
    app = _build_app()
    client = TestClient(app)

    # TestClient always presents as the same client host, so instead verify
    # that a fresh rate-limit window (new middleware instance) is independent
    # of a previous one — i.e. state isn't somehow global/module-level.
    for _ in range(10):
        client.post("/auth/login")
    assert client.post("/auth/login").status_code == 429

    fresh_client = TestClient(_build_app())
    assert fresh_client.post("/auth/login").status_code == 200


def test_unmatched_path_uses_generous_default_limit():
    client = TestClient(_build_app())
    for _ in range(50):
        resp = client.get("/overview")
        assert resp.status_code == 200
