from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    """Central configuration, loaded from environment variables / .env file.

    Every secret here must be supplied via environment in production — no
    defaults below are safe to use outside local development.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://ssc:ssc@localhost:5432/ssc",
        description="Async SQLAlchemy connection string for PostgreSQL.",
    )

    # Sessions / auth
    session_secret: str = Field(
        default=_INSECURE_DEFAULT_SECRET,
        description="Used to sign server-side session identifiers.",
    )
    session_cookie_name: str = "ssc_session"
    session_ttl_hours: int = 12
    session_cookie_samesite: str = Field(
        default="lax",
        description=(
            "'lax' works for local dev (frontend/backend on localhost, different ports). "
            "Production deployments with the frontend on a different domain (e.g. Vercel) "
            "than the backend MUST set this to 'none', which also forces the Secure flag."
        ),
    )
    csrf_cookie_name: str = "ssc_csrf"
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # Agent enrollment
    enrollment_token_ttl_minutes: int = 30
    agent_heartbeat_stale_seconds: int = 180

    # Monitoring
    default_check_interval_seconds: int = 60
    consecutive_failures_for_down: int = 3
    consecutive_successes_for_recovery: int = 2

    # Telegram
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_alert_cooldown_minutes: int = 30

    # CORS — the Vercel-hosted frontend origin(s), comma separated
    cors_allowed_origins: str = "http://localhost:3000"

    # The API's own public HTTPS URL, as agents and the install script will
    # reach it. Required in production — falls back to the incoming request's
    # URL only as a local-dev convenience, which is unreliable behind most
    # reverse proxies.
    public_api_url: str | None = None

    # Comma-separated hostnames this API will accept in the Host header
    # (Starlette's TrustedHostMiddleware). Must include the domain
    # PUBLIC_API_URL points at, since that's what your reverse proxy sends
    # as the Host header once it's configured to forward it.
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    # "testserver" is Starlette TestClient's fixed default Host header — safe
    # to always trust since it's not a producible value against a real
    # deployment, and tests exercising the real `app` instance need it.

    # Which immediate network peers this API trusts to set X-Forwarded-For /
    # X-Forwarded-Proto truthfully (uvicorn's ProxyHeadersMiddleware). The
    # default "*" is deliberate for this project's deployment topology, not
    # a generic shortcut: the API container's published port is bound to
    # 127.0.0.1 only (see docker-compose.yml), so the ONLY process that can
    # ever connect to it directly is the trusted reverse proxy on the same
    # host (aaPanel's Nginx) — there is no network path for an untrusted
    # party to reach this port and spoof these headers directly. If that
    # topology ever changes (e.g. the port is published more broadly, or
    # another proxy is added in front), this must be narrowed to the actual
    # trusted peer address(es) instead of left as "*".
    trusted_proxy_ips: str = "*"

    @property
    def trusted_hosts_list(self) -> list[str]:
        """Always includes PUBLIC_API_URL's own hostname automatically —
        requiring it to also be listed in TRUSTED_HOSTS would just be a
        second place to forget to update, and a mismatch here is a
        self-inflicted outage (every real request gets rejected), not a
        meaningful security boundary worth that footgun."""
        hosts = {h.strip() for h in self.trusted_hosts.split(",") if h.strip()}
        if self.public_api_url:
            parsed_host = urlparse(self.public_api_url).hostname
            if parsed_host:
                hosts.add(parsed_host)
        return list(hosts)

    # Metrics retention
    performance_metrics_retention_days: int = 90
    uptime_history_retention_days: int = 365

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_production_config(self) -> "Settings":
        """Fails fast at startup instead of silently running insecurely —
        a production deployment with the dev secret or wide-open CORS is a
        deployment blocker, not a warning."""
        if self.environment != "production":
            return self

        problems = []
        if self.session_secret == _INSECURE_DEFAULT_SECRET:
            problems.append("SESSION_SECRET is still the insecure development default")
        if len(self.session_secret) < 32:
            problems.append("SESSION_SECRET is too short (want 32+ random characters)")
        if self.cors_allowed_origins == "http://localhost:3000":
            problems.append("CORS_ALLOWED_ORIGINS is still the localhost default")
        if "*" in self.cors_origins_list:
            problems.append("CORS_ALLOWED_ORIGINS must not be '*' in production")
        if self.public_api_url is None:
            problems.append("PUBLIC_API_URL is not set — agent install commands would be wrong")
        if self.database_url.startswith("postgresql+asyncpg://ssc:ssc@localhost"):
            problems.append("DATABASE_URL is still the local-dev default")
        if self.session_cookie_samesite not in ("lax", "strict", "none"):
            problems.append("SESSION_COOKIE_SAMESITE must be 'lax', 'strict', or 'none'")

        if problems:
            raise ValueError(
                "Refusing to start with ENVIRONMENT=production and insecure configuration:\n"
                + "\n".join(f"  - {p}" for p in problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
