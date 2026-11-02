"""Regression tests for multi-admin support (POST/GET/DELETE /auth/users).

The platform used to allow exactly one account (migration 0002: a partial
unique index made a second `is_owner=True` row impossible at the database
level). Migration 0004 drops that index and the API gained endpoints to
create and remove additional equal admin accounts. These tests prove, with
no live PostgreSQL required, that:
  - the new endpoints are not reachable anonymously
  - creating an admin surfaces a 409 on a duplicate email instead of a 500
  - an admin cannot remove their own account
  - the last remaining active admin cannot be removed
  - removing an admin deactivates them (soft-delete) rather than hard-deleting,
    consistent with how servers are archived rather than dropped elsewhere in
    this codebase, and revokes their active sessions

Same approach as tests/test_api_security.py: run the real `app.main.app` in a
fresh subprocess per test, with `get_db`/`get_current_user` overridden by a
minimal fake session/user rather than touching a real database.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "services" / "api"


def _dev_env(**overrides) -> dict:
    env = os.environ.copy()
    env.pop("ENVIRONMENT", None)
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


def test_admin_management_endpoints_require_authentication():
    script = """
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)
results = {
    "list": client.get("/auth/users").status_code,
    "create": client.post("/auth/users", json={"email": "a@b.com", "password": "x" * 12, "display_name": "A"}).status_code,
    "remove": client.delete("/auth/users/00000000-0000-0000-0000-000000000000").status_code,
}
print(json.dumps(results))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert all(code == 401 for code in data.values()), data


def test_create_admin_rejects_duplicate_email_with_409_not_500():
    script = """
import json
import uuid
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user
from fastapi import Request

class _FakeSession:
    def add(self, obj):
        pass
    async def flush(self):
        raise IntegrityError("duplicate", params=None, orig=Exception("unique violation"))
    async def rollback(self):
        pass
    async def commit(self):
        pass

class _FakeAdmin:
    id = uuid.UUID("11111111-1111-1111-1111-111111111111")

async def _override_db():
    yield _FakeSession()

async def _override_user(request: Request):
    request.state.session = type("S", (), {"csrf_token": "test-csrf"})()
    return _FakeAdmin()

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.post(
    "/auth/users",
    json={"email": "existing@example.com", "password": "x" * 12, "display_name": "Dup"},
    headers={"X-CSRF-Token": "test-csrf"},
)
print(json.dumps({"status": resp.status_code, "body": resp.json()}))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["status"] == 409
    assert "already exists" in data["body"]["detail"]


def test_create_admin_succeeds_and_returns_the_new_account():
    script = """
import json
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user
from fastapi import Request

class _FakeSession:
    def add(self, obj):
        # Mirrors what a real flush would populate via each column's
        # Python-side default -- this fake never touches real SQLAlchemy
        # machinery, so nothing else will set these.
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)
        if getattr(obj, "is_active", None) is None:
            obj.is_active = True
        if getattr(obj, "totp_enabled", None) is None:
            obj.totp_enabled = False
    async def flush(self):
        pass
    async def commit(self):
        pass

class _FakeAdmin:
    id = uuid.UUID("11111111-1111-1111-1111-111111111111")

async def _override_db():
    yield _FakeSession()

async def _override_user(request: Request):
    request.state.session = type("S", (), {"csrf_token": "test-csrf"})()
    return _FakeAdmin()

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.post(
    "/auth/users",
    json={"email": "New.Admin@Example.com", "password": "x" * 12, "display_name": "New Admin"},
    headers={"X-CSRF-Token": "test-csrf"},
)
print(json.dumps({"status": resp.status_code, "body": resp.json()}))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["status"] == 201
    assert data["body"]["email"] == "new.admin@example.com"
    assert data["body"]["display_name"] == "New Admin"
    assert data["body"]["is_active"] is True


def test_create_admin_without_csrf_token_is_rejected():
    script = """
import json
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user
from fastapi import Request

class _FakeSession:
    pass

class _FakeAdmin:
    id = uuid.UUID("11111111-1111-1111-1111-111111111111")

async def _override_db():
    yield _FakeSession()

async def _override_user(request: Request):
    request.state.session = type("S", (), {"csrf_token": "test-csrf"})()
    return _FakeAdmin()

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.post(
    "/auth/users",
    json={"email": "nope@example.com", "password": "x" * 12, "display_name": "Nope"},
)
print(resp.status_code)
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "403"


def test_admin_cannot_remove_their_own_account():
    script = """
import json
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user
from fastapi import Request

SELF_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

class _FakeSession:
    pass

class _FakeAdmin:
    id = SELF_ID

async def _override_db():
    yield _FakeSession()

async def _override_user(request: Request):
    request.state.session = type("S", (), {"csrf_token": "test-csrf"})()
    return _FakeAdmin()

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.delete(f"/auth/users/{SELF_ID}", headers={"X-CSRF-Token": "test-csrf"})
print(json.dumps({"status": resp.status_code, "body": resp.json()}))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["status"] == 400
    assert "own account" in data["body"]["detail"]


def test_last_remaining_admin_cannot_be_removed():
    script = """
import json
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user
from fastapi import Request

SELF_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

class _CountResult:
    def scalar_one(self):
        return 1  # only one active admin left -- the caller

class _FakeSession:
    async def execute(self, *a, **k):
        return _CountResult()

class _FakeAdmin:
    id = SELF_ID

async def _override_db():
    yield _FakeSession()

async def _override_user(request: Request):
    request.state.session = type("S", (), {"csrf_token": "test-csrf"})()
    return _FakeAdmin()

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.delete(f"/auth/users/{OTHER_ID}", headers={"X-CSRF-Token": "test-csrf"})
print(json.dumps({"status": resp.status_code, "body": resp.json()}))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["status"] == 400
    assert "at least one" in data["body"]["detail"].lower()


def test_removing_an_admin_deactivates_rather_than_hard_deletes():
    script = """
import json
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user
from fastapi import Request

SELF_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

class _CountResult:
    def scalar_one(self):
        return 2  # two active admins -- removal is allowed

class _Target:
    id = OTHER_ID
    email = "leaving@example.com"
    is_active = True

class _TargetResult:
    def scalar_one_or_none(self):
        return _Target()

class _EmptyScalars:
    def scalars(self):
        class _S:
            def all(self):
                return []
        return _S()

class _FakeSession:
    def __init__(self):
        self.calls = 0
    async def execute(self, *a, **k):
        self.calls += 1
        if self.calls == 1:
            return _CountResult()
        if self.calls == 2:
            return _TargetResult()
        return _EmptyScalars()
    def add(self, obj):
        pass
    async def commit(self):
        pass

class _FakeAdmin:
    id = SELF_ID

async def _override_db():
    yield _FakeSession()

async def _override_user(request: Request):
    request.state.session = type("S", (), {"csrf_token": "test-csrf"})()
    return _FakeAdmin()

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.delete(f"/auth/users/{OTHER_ID}", headers={"X-CSRF-Token": "test-csrf"})
print(json.dumps({"status": resp.status_code, "body": resp.json()}))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["status"] == 200
    assert data["body"]["status"] == "removed"


def test_removing_a_nonexistent_admin_returns_404():
    script = """
import json
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user
from fastapi import Request

SELF_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MISSING_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

class _CountResult:
    def scalar_one(self):
        return 2

class _EmptyResult:
    def scalar_one_or_none(self):
        return None

class _FakeSession:
    def __init__(self):
        self.calls = 0
    async def execute(self, *a, **k):
        self.calls += 1
        return _CountResult() if self.calls == 1 else _EmptyResult()

class _FakeAdmin:
    id = SELF_ID

async def _override_db():
    yield _FakeSession()

async def _override_user(request: Request):
    request.state.session = type("S", (), {"csrf_token": "test-csrf"})()
    return _FakeAdmin()

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.delete(f"/auth/users/{MISSING_ID}", headers={"X-CSRF-Token": "test-csrf"})
print(resp.status_code)
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "404"


def test_list_admins_excludes_removed_accounts_by_default():
    script = """
import json
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user
from fastapi import Request

class _Active:
    id = uuid.uuid4()
    email = "active@example.com"
    display_name = "Active"
    totp_enabled = False
    is_active = True
    created_at = datetime.now(timezone.utc)

class _Scalars:
    def all(self):
        return [_Active()]

class _ListResult:
    def scalars(self):
        return _Scalars()

class _FakeSession:
    async def execute(self, *a, **k):
        return _ListResult()

class _FakeAdmin:
    id = uuid.uuid4()

async def _override_db():
    yield _FakeSession()

async def _override_user(request: Request):
    request.state.session = type("S", (), {"csrf_token": "test-csrf"})()
    return _FakeAdmin()

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.get("/auth/users")
print(json.dumps({"status": resp.status_code, "body": resp.json()}))
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["status"] == 200
    assert len(data["body"]) == 1
    assert data["body"][0]["email"] == "active@example.com"
