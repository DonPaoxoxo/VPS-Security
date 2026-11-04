"""Regression tests for the PDF report endpoint (GET /reports/pdf).

Same approach as tests/test_api_security.py and tests/test_auth_multi_admin.py:
run the real `app.main.app` in a fresh subprocess per test, with
`get_db`/`get_current_user` overridden by a minimal fake session/user rather
than touching a real database. The fake session answers every query with an
empty result, which is enough to prove the endpoint builds a real PDF end to
end without needing a live PostgreSQL.
"""

import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "services" / "api"

_FAKE_SESSION = """
class _FakeScalars:
    def all(self):
        return []

class _FakeResult:
    def scalars(self):
        return _FakeScalars()
    def scalar_one_or_none(self):
        return None
    def scalar_one(self):
        return 0

class _FakeSession:
    async def execute(self, query):
        return _FakeResult()

class _FakeAdmin:
    display_name = "Alex Rivera"
    email = "owner@example.com"

async def _override_db():
    yield _FakeSession()

async def _override_user():
    return _FakeAdmin()
"""


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


def test_reports_pdf_requires_authentication():
    script = """
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)
resp = client.get("/reports/pdf")
print(resp.status_code)
"""
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "401"


def test_reports_pdf_generates_a_real_pdf_with_no_data():
    script = (
        _FAKE_SESSION
        + """
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.get("/reports/pdf?start_date=2026-10-01&end_date=2026-10-31")
print(resp.status_code)
print(resp.headers.get("content-type"))
print(resp.headers.get("content-disposition"))
print(resp.content[:5])
"""
    )
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "200", lines
    assert lines[1] == "application/pdf"
    assert "security-report-2026-10-01_2026-10-31.pdf" in lines[2]
    assert lines[3] == "b'%PDF-'"


def test_reports_pdf_rejects_start_after_end():
    script = (
        _FAKE_SESSION
        + """
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.get("/reports/pdf?start_date=2026-10-31&end_date=2026-10-01")
print(resp.status_code)
"""
    )
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "400"


def test_reports_pdf_rejects_unknown_server():
    script = (
        _FAKE_SESSION
        + """
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_db, get_current_user

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user

client = TestClient(app, raise_server_exceptions=False)
resp = client.get("/reports/pdf?server_id=00000000-0000-0000-0000-000000000000")
print(resp.status_code)
"""
    )
    result = _run(script, _dev_env())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "404"
