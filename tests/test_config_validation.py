import os

import pytest

from ssc_core.config import Settings


@pytest.fixture
def clean_env(monkeypatch):
    for key in [
        "ENVIRONMENT",
        "SESSION_SECRET",
        "CORS_ALLOWED_ORIGINS",
        "PUBLIC_API_URL",
        "DATABASE_URL",
        "SESSION_COOKIE_SAMESITE",
    ]:
        monkeypatch.delenv(key, raising=False)
    yield monkeypatch


def test_development_defaults_do_not_raise(clean_env):
    Settings()  # environment defaults to "development" — insecure defaults are fine there


def test_production_with_defaults_is_refused(clean_env):
    clean_env.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="insecure configuration"):
        Settings()


def test_production_with_proper_overrides_succeeds(clean_env):
    clean_env.setenv("ENVIRONMENT", "production")
    clean_env.setenv("SESSION_SECRET", "x" * 40)
    clean_env.setenv("CORS_ALLOWED_ORIGINS", "https://dashboard.example.com")
    clean_env.setenv("PUBLIC_API_URL", "https://hub.example.com")
    clean_env.setenv("DATABASE_URL", "postgresql+asyncpg://real:real@realhost:5432/real")
    clean_env.setenv("SESSION_COOKIE_SAMESITE", "none")

    settings = Settings()
    assert settings.public_api_url == "https://hub.example.com"


def test_production_rejects_wildcard_cors(clean_env):
    clean_env.setenv("ENVIRONMENT", "production")
    clean_env.setenv("SESSION_SECRET", "x" * 40)
    clean_env.setenv("CORS_ALLOWED_ORIGINS", "*")
    clean_env.setenv("PUBLIC_API_URL", "https://hub.example.com")
    clean_env.setenv("DATABASE_URL", "postgresql+asyncpg://real:real@realhost:5432/real")
    clean_env.setenv("SESSION_COOKIE_SAMESITE", "none")

    with pytest.raises(ValueError, match="must not be '\\*'"):
        Settings()
