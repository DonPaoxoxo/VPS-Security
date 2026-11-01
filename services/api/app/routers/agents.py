import os
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_agent
from app.schemas.agents import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    AgentEventsBatchSubmit,
    DiscoverySubmitRequest,
    DiscoverySubmitResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.services.discovery import process_discovery_submission
from ssc_core.config import get_settings
from ssc_core.models.monitoring import PerformanceMetric
from ssc_core.models.security import FileIntegrityEvent, LoginEvent, SecurityEvent
from ssc_core.models.server import AapanelInstance, AgentEnrollmentToken, AgentStatus, MonitoringAgent, Server
from ssc_core.security import generate_token, hash_token

router = APIRouter(prefix="/agents", tags=["agents"])
settings = get_settings()

# In the Docker image, the Dockerfile pre-builds this tarball at build time
# from agents/linux so it can never drift from the code actually running.
# In local dev (no such prebuilt file), we build it on the fly from the
# monorepo-relative path and cache it for the life of the process.
_PREBUILT_BUNDLE_PATH = Path(os.environ.get("AGENT_BUNDLE_PATH", "/srv/agent-bundle.tar.gz"))
_DEV_AGENT_SOURCE_DIR = Path(__file__).resolve().parents[4] / "agents" / "linux"
_dev_bundle_cache: Path | None = None


def _resolve_agent_bundle_path() -> Path:
    global _dev_bundle_cache
    if _PREBUILT_BUNDLE_PATH.exists():
        return _PREBUILT_BUNDLE_PATH

    if _dev_bundle_cache is not None and _dev_bundle_cache.exists():
        return _dev_bundle_cache

    if not _DEV_AGENT_SOURCE_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent install bundle is not available on this deployment",
        )

    tmp = Path(tempfile.gettempdir()) / "ssc-agent-bundle-dev.tar.gz"
    with tarfile.open(tmp, "w:gz") as tar:
        for item in _DEV_AGENT_SOURCE_DIR.iterdir():
            if item.name in ("__pycache__",):
                continue
            tar.add(item, arcname=item.name)
    _dev_bundle_cache = tmp
    return tmp


@router.get("/install-bundle.tar.gz")
async def download_install_bundle() -> FileResponse:
    """Serves the agent source code as a tarball so the one-line install
    command in the Add Server Wizard is self-contained. Intentionally
    unauthenticated — it contains only our own code, no secrets, and must be
    fetchable before an agent has any credentials."""
    path = _resolve_agent_bundle_path()
    return FileResponse(path, media_type="application/gzip", filename="ssc-agent-bundle.tar.gz")


@router.post("/enroll", response_model=AgentEnrollResponse)
async def enroll_agent(payload: AgentEnrollRequest, db: AsyncSession = Depends(get_db)) -> AgentEnrollResponse:
    """Exchanges a one-time enrollment token for a permanent, independently
    revocable agent API key. The token is consumed on first successful use."""
    token_hash = hash_token(payload.enrollment_token)
    result = await db.execute(select(AgentEnrollmentToken).where(AgentEnrollmentToken.token_hash == token_hash))
    token_row = result.scalar_one_or_none()

    if token_row is None or token_row.used_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Enrollment token invalid or already used")
    if token_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Enrollment token expired")

    existing = await db.execute(select(MonitoringAgent).where(MonitoringAgent.server_id == token_row.server_id))
    agent = existing.scalar_one_or_none()

    raw_api_key = generate_token()
    if agent is None:
        agent = MonitoringAgent(
            server_id=token_row.server_id,
            api_key_hash=hash_token(raw_api_key),
            status=AgentStatus.connected,
            agent_version=payload.agent_version,
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        db.add(agent)
    else:
        # Re-enrollment replaces the credential; the old key is implicitly
        # dead because its hash no longer matches anything stored.
        agent.api_key_hash = hash_token(raw_api_key)
        agent.status = AgentStatus.connected
        agent.agent_version = payload.agent_version
        agent.revoked_at = None
        agent.last_heartbeat_at = datetime.now(timezone.utc)

    token_row.used_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()

    return AgentEnrollResponse(agent_id=agent.id, server_id=agent.server_id, api_key=raw_api_key)


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    payload: HeartbeatRequest, agent: MonitoringAgent = Depends(require_agent), db: AsyncSession = Depends(get_db)
) -> HeartbeatResponse:
    agent.status = AgentStatus.connected
    agent.last_heartbeat_at = datetime.now(timezone.utc)
    agent.agent_version = payload.agent_version or agent.agent_version
    agent.last_reported_os = payload.operating_system or agent.last_reported_os
    agent.last_reported_cpu_pct = payload.cpu_pct
    agent.last_reported_ram_pct = payload.ram_pct
    agent.last_reported_disk_pct = payload.disk_pct

    if payload.operating_system:
        await db.execute(
            update(Server).where(Server.id == agent.server_id).values(operating_system=payload.operating_system)
        )

    if payload.aapanel_local_status:
        result = await db.execute(select(AapanelInstance).where(AapanelInstance.server_id == agent.server_id))
        instance = result.scalar_one_or_none()
        if instance is not None:
            instance.last_agent_reported_local_status = payload.aapanel_local_status

    db.add(
        PerformanceMetric(
            server_id=agent.server_id,
            recorded_at=datetime.now(timezone.utc),
            cpu_pct=payload.cpu_pct,
            ram_pct=payload.ram_pct,
            disk_pct=payload.disk_pct,
            load_average=payload.load_average,
            network_rx_bytes=payload.network_rx_bytes,
            network_tx_bytes=payload.network_tx_bytes,
            service_status=payload.service_status,
        )
    )

    await db.commit()
    return HeartbeatResponse(received_at=datetime.now(timezone.utc), server_id=agent.server_id)


@router.post("/discovery", response_model=DiscoverySubmitResponse)
async def submit_discovery(
    payload: DiscoverySubmitRequest, agent: MonitoringAgent = Depends(require_agent), db: AsyncSession = Depends(get_db)
) -> DiscoverySubmitResponse:
    run = await process_discovery_submission(db, agent.server_id, payload)
    await db.commit()
    return DiscoverySubmitResponse(
        discovery_run_id=run.id, websites_found=run.websites_found, websites_new=run.websites_new
    )


@router.post("/events")
async def submit_events(
    payload: AgentEventsBatchSubmit,
    agent: MonitoringAgent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
) -> dict:
    for e in payload.security_events:
        db.add(
            SecurityEvent(
                server_id=agent.server_id,
                event_type=e.event_type,
                severity=e.severity,
                occurred_at=e.occurred_at,
                source_ip=e.source_ip,
                account=e.account,
                evidence=e.evidence,
            )
        )
    for e in payload.login_events:
        db.add(
            LoginEvent(
                server_id=agent.server_id,
                occurred_at=e.occurred_at,
                was_successful=e.was_successful,
                source_ip=e.source_ip,
                account=e.account,
                auth_method=e.auth_method,
            )
        )
    for e in payload.file_integrity_events:
        db.add(
            FileIntegrityEvent(
                server_id=agent.server_id,
                file_path=e.file_path,
                change_type=e.change_type,
                detected_at=e.detected_at,
                previous_hash=e.previous_hash,
                new_hash=e.new_hash,
                responsible_account=e.responsible_account,
                responsible_process=e.responsible_process,
            )
        )
    await db.commit()
    return {
        "received": {
            "security_events": len(payload.security_events),
            "login_events": len(payload.login_events),
            "file_integrity_events": len(payload.file_integrity_events),
        }
    }
