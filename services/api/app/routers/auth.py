from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    MfaEnableResponse,
    MfaVerifyRequest,
    OwnerSetupRequest,
)
from app.services.audit import record_audit
from ssc_core.config import get_settings
from ssc_core.models.user import User, UserSession
from ssc_core.security import generate_token, hash_password, hash_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.get("/setup-required")
async def setup_required(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(User).limit(1))
    return {"setup_required": result.scalar_one_or_none() is None}


@router.post("/setup", status_code=status.HTTP_201_CREATED)
async def setup_owner(payload: OwnerSetupRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Creates the single owner account. Only works while no account exists —
    there is no public registration after that.

    The existence check below is a (deliberately cheap) pre-check for the
    common case, not the actual guarantee — two concurrent requests could
    both pass it before either commits. The real guarantee is the partial
    unique index `ix_users_singleton_owner` (migration 0002), which makes a
    second owner row impossible at the database level regardless of timing;
    a race here surfaces as an IntegrityError, caught below and turned into
    the same 409 the pre-check would have given serially.
    """
    existing = await db.execute(select(User).limit(1))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Owner account already exists")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_owner=True,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Owner account already exists")
    return {"status": "created"}


async def _issue_session(db: AsyncSession, user: User, request: Request, response: Response) -> str:
    raw_token = generate_token()
    csrf_token = generate_token(16)
    session_row = UserSession(
        user_id=user.id,
        session_token_hash=hash_token(raw_token),
        csrf_token=csrf_token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session_row)
    await db.flush()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.environment != "development" or settings.session_cookie_samesite == "none",
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return csrf_token


@router.post("/login")
async def login(
    payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> CurrentUserResponse:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    generic_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user is None:
        raise generic_error

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        # Deliberately the same 401 as "no such user" / "wrong password" below —
        # a distinct status/message here would let an unauthenticated caller
        # confirm an account exists simply by locking it out and comparing
        # responses to a made-up email, which never reaches this branch.
        raise generic_error

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.login_max_attempts:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.login_lockout_minutes
            )
            user.failed_login_attempts = 0
        await db.commit()
        raise generic_error

    if user.totp_enabled:
        if not payload.totp_code or not pyotp.TOTP(user.totp_secret).verify(payload.totp_code, valid_window=1):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing MFA code")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)

    csrf_token = await _issue_session(db, user, request, response)
    await record_audit(
        db,
        user_id=user.id,
        action="login",
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return CurrentUserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        totp_enabled=user.totp_enabled,
        csrf_token=csrf_token,
    )


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        token_hash = hash_token(token)
        result = await db.execute(select(UserSession).where(UserSession.session_token_hash == token_hash))
        session_row = result.scalar_one_or_none()
        if session_row:
            session_row.revoked_at = datetime.now(timezone.utc)
            await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"status": "logged_out"}


@router.get("/me")
async def me(request: Request, user: User = Depends(get_current_user)) -> CurrentUserResponse:
    session_row: UserSession = request.state.session
    return CurrentUserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        totp_enabled=user.totp_enabled,
        csrf_token=session_row.csrf_token,
    )


@router.post("/mfa/enable")
async def enable_mfa(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> MfaEnableResponse:
    secret = pyotp.random_base32()
    user.totp_secret = secret
    user.totp_enabled = False  # enabled only once verified
    await db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Server Security Center")
    return MfaEnableResponse(secret=secret, qr_uri=uri)


@router.post("/mfa/verify")
async def verify_mfa(
    payload: MfaVerifyRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    if not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(payload.totp_code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")
    user.totp_enabled = True
    await db.commit()
    return {"status": "mfa_enabled"}
