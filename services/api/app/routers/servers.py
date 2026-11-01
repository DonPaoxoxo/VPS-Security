from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_current_user, get_db, require_csrf
from app.schemas.servers import (
    EnrollmentTokenResponse,
    ServerCreateRequest,
    ServerGroupCreateRequest,
    ServerResponse,
    ServerUpdateRequest,
)
from app.services.audit import record_audit
from ssc_core.config import get_settings
from ssc_core.models.server import (
    AapanelInstance,
    AgentEnrollmentToken,
    AgentStatus,
    MonitoringAgent,
    Server,
    ServerGroup,
)
from ssc_core.models.user import User
from ssc_core.security import generate_token, hash_token

router = APIRouter(prefix="/servers", tags=["servers"], dependencies=[Depends(get_current_user)])
settings = get_settings()


def _to_response(server: Server) -> ServerResponse:
    return ServerResponse(
        id=server.id,
        name=server.name,
        hostname_or_ip=server.hostname_or_ip,
        provider=server.provider,
        country=server.country,
        operating_system=server.operating_system,
        group_id=server.group_id,
        has_aapanel=server.has_aapanel,
        monitoring_status=server.monitoring_status,
        is_archived=server.is_archived,
        registered_at=server.registered_at,
        agent_status=server.agent.status.value if server.agent else None,
        last_heartbeat_at=server.agent.last_heartbeat_at if server.agent else None,
        aapanel_status=server.aapanel_instance.status.value if server.aapanel_instance else None,
        cpu_pct=server.agent.last_reported_cpu_pct if server.agent else None,
        ram_pct=server.agent.last_reported_ram_pct if server.agent else None,
        disk_pct=server.agent.last_reported_disk_pct if server.agent else None,
    )


@router.get("", response_model=list[ServerResponse])
async def list_servers(db: AsyncSession = Depends(get_db), include_archived: bool = False) -> list[ServerResponse]:
    query = select(Server).options(selectinload(Server.agent), selectinload(Server.aapanel_instance))
    if not include_archived:
        query = query.where(Server.is_archived.is_(False))
    result = await db.execute(query.order_by(Server.name))
    return [_to_response(s) for s in result.scalars().all()]


@router.post("", response_model=ServerResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
async def create_server(
    payload: ServerCreateRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> ServerResponse:
    server = Server(
        name=payload.name,
        hostname_or_ip=payload.hostname_or_ip,
        provider=payload.provider,
        country=payload.country,
        has_aapanel=payload.has_aapanel,
        group_id=payload.group_id,
        registered_at=datetime.now(timezone.utc),
    )
    db.add(server)
    await db.flush()

    if payload.has_aapanel and payload.aapanel_endpoint_url:
        db.add(
            AapanelInstance(
                server_id=server.id,
                endpoint_url=payload.aapanel_endpoint_url,
                port=payload.aapanel_port or 8888,
            )
        )

    await record_audit(db, user_id=user.id, action="server.create", resource_type="server", resource_id=str(server.id))
    await db.commit()
    await db.refresh(server)
    server.agent = None
    server.aapanel_instance = None
    return _to_response(server)


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(server_id: UUID, db: AsyncSession = Depends(get_db)) -> ServerResponse:
    result = await db.execute(
        select(Server)
        .options(selectinload(Server.agent), selectinload(Server.aapanel_instance))
        .where(Server.id == server_id)
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return _to_response(server)


@router.patch("/{server_id}", response_model=ServerResponse, dependencies=[Depends(require_csrf)])
async def update_server(
    server_id: UUID,
    payload: ServerUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ServerResponse:
    result = await db.execute(
        select(Server)
        .options(selectinload(Server.agent), selectinload(Server.aapanel_instance))
        .where(Server.id == server_id)
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(server, field, value)

    await record_audit(db, user_id=user.id, action="server.update", resource_type="server", resource_id=str(server_id))
    await db.commit()
    return _to_response(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
async def archive_server(
    server_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    """Archives rather than hard-deletes, preserving history (uptime, security
    events, discovered websites) for a server that is retired."""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    server.is_archived = True
    server.monitoring_status = "archived"
    await record_audit(db, user_id=user.id, action="server.archive", resource_type="server", resource_id=str(server_id))
    await db.commit()


@router.post("/{server_id}/agent/revoke", dependencies=[Depends(require_csrf)])
async def revoke_agent(
    server_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    """Immediately invalidates this server's agent API key. The agent process
    keeps running on the remote host but every request it makes will be
    rejected (require_agent looks up the key's hash, not the server) until
    it's re-enrolled with a fresh token."""
    result = await db.execute(select(MonitoringAgent).where(MonitoringAgent.server_id == server_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No agent enrolled for this server")

    agent.revoked_at = datetime.now(timezone.utc)
    agent.status = AgentStatus.disconnected
    await record_audit(db, user_id=user.id, action="server.agent_revoked", resource_type="server", resource_id=str(server_id))
    await db.commit()
    return {"status": "revoked"}


@router.post(
    "/{server_id}/enrollment-token",
    response_model=EnrollmentTokenResponse,
    dependencies=[Depends(require_csrf)],
)
async def create_enrollment_token(
    server_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EnrollmentTokenResponse:
    """Add Server Wizard step 2: generates a short-lived, single-use token the
    agent install script exchanges for its own permanent, independently
    revocable API key."""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    raw_token = generate_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.enrollment_token_ttl_minutes)
    db.add(AgentEnrollmentToken(server_id=server_id, token_hash=hash_token(raw_token), expires_at=expires_at))

    await record_audit(db, user_id=user.id, action="server.enrollment_token_issued", resource_type="server", resource_id=str(server_id))
    await db.commit()

    if settings.public_api_url:
        api_base = settings.public_api_url.rstrip("/")
    else:
        # Local-dev convenience only: unreliable behind most reverse proxies,
        # which is exactly why PUBLIC_API_URL is a hard requirement in
        # production (see Settings._validate_production_config).
        api_base = str(request.base_url).rstrip("/")

    install_command = (
        f"curl -fsSL {api_base}/agents/install-bundle.tar.gz -o /tmp/ssc-agent-bundle.tar.gz && "
        f"mkdir -p /tmp/ssc-agent-install && "
        f"tar -xzf /tmp/ssc-agent-bundle.tar.gz -C /tmp/ssc-agent-install && "
        f"cd /tmp/ssc-agent-install && "
        f"sudo ./install.sh --api-url {api_base} --token {raw_token}"
    )
    return EnrollmentTokenResponse(
        server_id=server_id, enrollment_token=raw_token, expires_at=expires_at, install_command=install_command
    )


@router.get("/groups/all")
async def list_groups(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(ServerGroup).order_by(ServerGroup.name))
    return [{"id": str(g.id), "name": g.name, "description": g.description} for g in result.scalars().all()]


@router.post("/groups", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
async def create_group(payload: ServerGroupCreateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    group = ServerGroup(name=payload.name, description=payload.description)
    db.add(group)
    await db.commit()
    return {"id": str(group.id), "name": group.name}
