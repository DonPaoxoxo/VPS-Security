import hmac
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ssc_core.config import Settings, get_settings
from ssc_core.db import AsyncSessionLocal
from ssc_core.models.server import MonitoringAgent
from ssc_core.models.user import User, UserSession
from ssc_core.security import hash_token

settings = get_settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validates the HTTP-only session cookie and returns the owning user.
    Raises 401 if missing, expired, or revoked."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_hash = hash_token(token)
    result = await db.execute(select(UserSession).where(UserSession.session_token_hash == token_hash))
    session_row = result.scalar_one_or_none()
    if session_row is None or session_row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid")
    if session_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user_result = await db.execute(select(User).where(User.id == session_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled")

    request.state.session = session_row
    return user


async def require_csrf(request: Request, _user: User = Depends(get_current_user)) -> None:
    """Mutating requests must echo the per-session CSRF token in a header,
    proving the caller can read the dashboard's own cookies (same-origin).
    Depends on get_current_user so request.state.session is always populated first."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    header_token = request.headers.get("X-CSRF-Token")
    session_row: UserSession | None = getattr(request.state, "session", None)
    if (
        session_row is None
        or header_token is None
        or not hmac.compare_digest(header_token, session_row.csrf_token)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


async def require_agent(
    db: AsyncSession = Depends(get_db),
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> MonitoringAgent:
    """Authenticates an inbound agent request by its per-server API key."""
    if not x_agent_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing agent credentials")

    key_hash = hash_token(x_agent_key)
    result = await db.execute(select(MonitoringAgent).where(MonitoringAgent.api_key_hash == key_hash))
    agent = result.scalar_one_or_none()
    if agent is None or agent.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Agent credentials revoked or invalid")
    return agent


def get_app_settings() -> Settings:
    return settings
