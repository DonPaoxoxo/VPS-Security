"""Security audit: proves anonymous access is denied to sensitive endpoints,
production hardening (docs gating, trusted hosts, no-store headers, proxy
header trust) actually takes effect, and the login/setup fixes from this
audit close the findings they were meant to close.

Everything here runs the REAL `app.main.app` — in a fresh subprocess per
test group, never the parent pytest process, so there's no risk of
`get_settings()`'s process-wide `lru_cache` picking up a stale config from
another test file, and no risk of cross-test environment leakage. A real
PostgreSQL is not required: an anonymous request with no session cookie is
rejected by `get_current_user` before it ever touches `db.execute(...)` —
SQLAlchemy's async engine/session are lazy and never open a connection until
first used, confirmed by the fact these tests pass with a DATABASE_URL that
points at a host that doesn't exist.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "services" / "api"


def _dev_env(**overrides) -> dict:
    env = os.environ.copy()
    env.pop("ENVIRONMENT", None)  # defaults to "development" — no production validation required
    env.update(overrides)
    return env


def _production_env(**overrides) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "production",
            "SESSION_SECRET": "x" * 40,
            "CORS_ALLOWED_ORIGINS": "https://dashboard.example.com",
            "PUBLIC_API_URL": "https://security-api.yono777hub.com",
            "DATABASE_URL": "postgresql+asyncpg://real:real@realhost-that-does-not-exist:5432/real",
            "SESSION_COOKIE_SAMESITE": "none",
        }
    )
    env.update(overrides)
    return env


def _run(code: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(API_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


_PROBE_SCRIPT = """
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)
probes = json.loads('''{probes}''')
results = {{}}
for key, method, path in probes:
    resp = getattr(client, method)(path)
    results[key] = resp.status_code
print(json.dumps(results))
"""


def _probe_anonymous(probes: list[tuple[str, str, str]], env: dict | None = None) -> dict:
    """probes: list of (key, http_method_lowercase, path). Returns {key: status_code}."""
    script = _PROBE_SCRIPT.format(probes=json.dumps(probes))
    result = _run(script, env or _dev_env())
    assert result.returncode == 0, f"probe script failed: {result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


# --- Task 1.1-1.6: anonymous access must be denied to sensitive endpoints --


def test_server_inventory_requires_authentication():
    results = _probe_anonymous(
        [
            ("list", "get", "/servers"),
            ("groups", "get", "/servers/groups/all"),
            ("detail", "get", "/servers/00000000-0000-0000-0000-000000000000"),
        ]
    )
    assert all(code == 401 for code in results.values()), results


def test_security_event_data_requires_authentication():
    results = _probe_anonymous(
        [
            ("security_events", "get", "/security-events"),
            ("login_events", "get", "/login-events"),
            ("file_integrity", "get", "/file-integrity-events"),
            ("ip_investigation", "get", "/ip-investigation"),
            ("incidents", "get", "/incidents"),
        ]
    )
    assert all(code == 401 for code in results.values()), results


def test_administrative_endpoints_require_authentication():
    results = _probe_anonymous(
        [
            ("settings", "get", "/settings/telegram"),
            ("audit_logs", "get", "/audit-logs"),
            ("overview", "get", "/overview"),
            ("alerts", "get", "/alerts"),
            ("aapanel", "get", "/aapanel"),
            ("domains", "get", "/domains"),
        ]
    )
    assert all(code == 401 for code in results.values()), results


def test_monitoring_configuration_cannot_be_modified_anonymously():
    results = _probe_anonymous(
        [
            ("create_server", "post", "/servers"),
            ("telegram_settings", "put", "/settings/telegram"),
            ("domain_review", "post", "/domains/review"),
            ("alert_ack", "post", "/alerts/00000000-0000-0000-0000-000000000000/acknowledge"),
        ]
    )
    # 401 (no session) is correct here; the CSRF check (which would give 403)
    # never even runs because get_current_user rejects first.
    assert all(code == 401 for code in results.values()), results


def test_agent_endpoints_reject_missing_or_invalid_credentials():
    results = _probe_anonymous(
        [
            ("heartbeat_no_key", "post", "/agents/heartbeat"),
            ("discovery_no_key", "post", "/agents/discovery"),
            ("events_no_key", "post", "/agents/events"),
        ]
    )
    assert all(code == 401 for code in results.values()), results


def test_login_gives_identical_response_for_nonexistent_and_locked_accounts():
    """Closes an account-enumeration finding from this audit: the lockout
    response used to be HTTP 423 with a distinct message, which only ever
    fired for a REAL existing account — letting an unauthenticated caller
    confirm an account exists by deliberately locking it out. Both branches
    must now be indistinguishable."""
    script = """
import json
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db

class _Result:
    def __init__(self, user):
        self._user = user
    def scalar_one_or_none(self):
        return self._user

class _FakeSession:
    def __init__(self, user):
        self._user = user
    async def execute(self, *a, **k):
        return _Result(self._user)
    async def commit(self):
        pass

class _LockedUser:
    id = "00000000-0000-0000-0000-000000000000"
    email = "locked@example.com"
    password_hash = "irrelevant"
    failed_login_attempts = 0
    locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)
    totp_enabled = False
    is_active = True

async def _override_none():
    yield _FakeSession(None)

async def _override_locked():
    yield _FakeSession(_LockedUser())

client = TestClient(app, raise_server_exceptions=False)

app.dependency_overrides[get_db] = _override_none
r1 = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})

app.dependency_overrides[get_db] = _override_locked
r2 = client.post("/auth/login", json={"email": "locked@example.com", "password": "wrong"})

print(json.dumps({"nonexistent": [r1.status_code, r1.json()], "locked": [r2.status_code, r2.json()]}))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["nonexistent"] == data["locked"], data
    assert data["nonexistent"][0] == 401


def test_setup_owner_handles_concurrent_creation_via_db_constraint():
    """Closes the TOCTOU race from this audit: the pre-check ('does a user
    already exist?') and the INSERT are not atomic. The real guarantee is
    the partial unique index added in migration 0002 (untested here — no
    live PostgreSQL in this environment); this test instead proves the
    application-level handling of that constraint firing is correct, by
    simulating the race as the DB raising IntegrityError at commit time even
    though the pre-check saw no existing user."""
    script = """
import json
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db

class _Result:
    def scalar_one_or_none(self):
        return None  # pre-check sees no existing user -- the race window

class _FakeSession:
    def add(self, obj):
        pass
    async def execute(self, *a, **k):
        return _Result()
    async def commit(self):
        raise IntegrityError("duplicate", params=None, orig=Exception("unique violation"))
    async def rollback(self):
        pass

async def _override():
    yield _FakeSession()

client = TestClient(app, raise_server_exceptions=False)
app.dependency_overrides[get_db] = _override
resp = client.post("/auth/setup", json={"email": "race@example.com", "password": "a" * 16, "display_name": "Race"})
print(json.dumps({"status": resp.status_code, "body": resp.json()}))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["status"] == 409
    assert "already exists" in data["body"]["detail"]


def test_enroll_without_token_is_rejected():
    """/agents/enroll always queries the DB to look up the token — unlike the
    get_current_user-gated routes above, there's no DB-free rejection path
    here, so this needs a mocked session (an empty-result lookup, i.e. 'no
    such token') rather than relying on a real connection failing fast. On
    this Windows dev box, connecting to a non-listening localhost:5432 does
    NOT fail fast — it hangs until a ~30s OS-level timeout, which is exactly
    the bug this mock avoids depending on."""
    script = """
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db

class _Result:
    def scalar_one_or_none(self):
        return None  # no enrollment token matches this hash

class _FakeSession:
    async def execute(self, *a, **k):
        return _Result()

async def _override():
    yield _FakeSession()

app.dependency_overrides[get_db] = _override
client = TestClient(app, raise_server_exceptions=False)
resp = client.post("/agents/enroll", json={"enrollment_token": "not-a-real-token"})
print(resp.status_code)
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "401"


# --- Task 1.9/1.10: caching and docs exposure -------------------------------


def test_public_endpoint_responses_are_not_cacheable():
    script = """
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app, raise_server_exceptions=False)
resp = client.get("/health")
print(resp.headers.get("cache-control"))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "no-store, private"


def test_docs_are_disabled_in_production():
    script = """
from app.main import app
print(app.docs_url)
print(app.redoc_url)
print(app.openapi_url)
"""
    result = _run(script, _production_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["None", "None", "None"]


def test_docs_are_available_in_development():
    script = """
from app.main import app
print(app.docs_url)
print(app.openapi_url)
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["/docs", "/openapi.json"]


def test_openapi_schema_still_generates_with_docs_disabled():
    """Disabling the public /docs route must not break schema generation
    itself — only its public exposure."""
    script = """
from app.main import app
schema = app.openapi()
print(len(schema["paths"]))
"""
    result = _run(script, _production_env())
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) > 30


# --- Task 3: trusted reverse-proxy settings ---------------------------------


def test_trusted_host_middleware_rejects_unrecognized_host():
    script = """
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app, base_url="http://evil-attacker-host.example", raise_server_exceptions=False)
resp = client.get("/health")
print(resp.status_code)
"""
    result = _run(script, _production_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "400"


def test_trusted_host_middleware_accepts_the_real_public_api_domain():
    script = """
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app, base_url="https://security-api.yono777hub.com", raise_server_exceptions=False)
resp = client.get("/health")
print(resp.status_code)
"""
    result = _run(script, _production_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "200"


def test_proxy_headers_middleware_is_applied_before_rate_limiter():
    """Regression test for the ordering bug caught during this audit: if
    ProxyHeadersMiddleware were registered inner (not outer) relative to
    RateLimitMiddleware, every request would appear to come from the same
    address (the reverse proxy's), and distinct real clients would share one
    rate-limit bucket. With the correct order, two different
    X-Forwarded-For values are tracked independently.

    Must use a strictly-limited path (10/min) to make bucketing observable
    within 10 requests — only /auth/login, /auth/setup, /agents/enroll
    qualify, and all three touch the DB in their handler body. The 429
    signal this test checks is decided entirely by RateLimitMiddleware
    BEFORE the request reaches the route handler, so the DB is mocked out
    (empty-result 'no such user') purely so the requests return quickly and
    deterministically — a real connection attempt to a non-listening
    localhost:5432 hangs for ~30s on this dev box rather than failing fast.
    """
    script = """
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db

class _Result:
    def scalar_one_or_none(self):
        return None

class _FakeSession:
    async def execute(self, *a, **k):
        return _Result()

async def _override():
    yield _FakeSession()

app.dependency_overrides[get_db] = _override
client = TestClient(app, raise_server_exceptions=False)

def hits(ip):
    codes = []
    for _ in range(10):
        codes.append(client.post("/auth/login", json={"email": "a@b.com", "password": "x"}, headers={"X-Forwarded-For": ip}).status_code)
    return codes

first_ip_codes = hits("203.0.113.10")
second_ip_codes = hits("203.0.113.20")
# Both IPs should get through their own first 10 requests without being
# rate-limited by each other (429 would mean they're sharing one bucket).
print(429 in first_ip_codes, 429 in second_ip_codes)
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False False"
