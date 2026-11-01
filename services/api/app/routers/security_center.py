from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_current_user, get_db, require_csrf
from app.schemas.misc import (
    DowntimeIncidentResponse,
    FileIntegrityEventResponse,
    IpInvestigationResponse,
    LoginEventResponse,
    SecurityEventResponse,
)
from ssc_core.models.monitoring import DowntimeIncident
from ssc_core.models.security import FileIntegrityEvent, LoginEvent, ObservedIpAddress, SecurityEvent
from ssc_core.models.server import Server

router = APIRouter(tags=["security"], dependencies=[Depends(get_current_user)])


@router.get("/security-events", response_model=list[SecurityEventResponse])
async def list_security_events(
    db: AsyncSession = Depends(get_db), server_id: UUID | None = None, limit: int = 200
) -> list[SecurityEventResponse]:
    query = select(SecurityEvent).options(selectinload(SecurityEvent.server)).order_by(SecurityEvent.occurred_at.desc()).limit(limit)
    if server_id:
        query = query.where(SecurityEvent.server_id == server_id)
    result = await db.execute(query)
    return [
        SecurityEventResponse(
            id=e.id,
            server_id=e.server_id,
            server_name=e.server.name if e.server else None,
            event_type=e.event_type,
            severity=e.severity.value,
            occurred_at=e.occurred_at,
            source_ip=e.source_ip,
            account=e.account,
            evidence=e.evidence,
            investigation_status=e.investigation_status.value,
        )
        for e in result.scalars().all()
    ]


@router.patch("/security-events/{event_id}/status", dependencies=[Depends(require_csrf)])
async def update_investigation_status(event_id: UUID, new_status: str, db: AsyncSession = Depends(get_db)) -> dict:
    from ssc_core.models.security import InvestigationStatus

    result = await db.execute(select(SecurityEvent).where(SecurityEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event.investigation_status = InvestigationStatus(new_status)
    await db.commit()
    return {"status": "updated"}


@router.get("/login-events", response_model=list[LoginEventResponse])
async def list_login_events(
    db: AsyncSession = Depends(get_db),
    server_id: UUID | None = None,
    only_failed: bool = False,
    limit: int = 200,
) -> list[LoginEventResponse]:
    query = select(LoginEvent).options(selectinload(LoginEvent.server)).order_by(LoginEvent.occurred_at.desc()).limit(limit)
    if server_id:
        query = query.where(LoginEvent.server_id == server_id)
    if only_failed:
        query = query.where(LoginEvent.was_successful.is_(False))
    result = await db.execute(query)
    return [
        LoginEventResponse(
            id=e.id,
            server_id=e.server_id,
            server_name=e.server.name if e.server else None,
            occurred_at=e.occurred_at,
            was_successful=e.was_successful,
            source_ip=e.source_ip,
            account=e.account,
            auth_method=e.auth_method,
        )
        for e in result.scalars().all()
    ]


@router.get("/file-integrity-events", response_model=list[FileIntegrityEventResponse])
async def list_file_integrity_events(
    db: AsyncSession = Depends(get_db), server_id: UUID | None = None, limit: int = 200
) -> list[FileIntegrityEventResponse]:
    query = (
        select(FileIntegrityEvent)
        .options(selectinload(FileIntegrityEvent.server))
        .order_by(FileIntegrityEvent.detected_at.desc())
        .limit(limit)
    )
    if server_id:
        query = query.where(FileIntegrityEvent.server_id == server_id)
    result = await db.execute(query)
    return [
        FileIntegrityEventResponse(
            id=e.id,
            server_id=e.server_id,
            server_name=e.server.name if e.server else None,
            file_path=e.file_path,
            change_type=e.change_type,
            detected_at=e.detected_at,
            previous_hash=e.previous_hash,
            new_hash=e.new_hash,
            responsible_account=e.responsible_account,
            responsible_process=e.responsible_process,
            is_approved_change=e.is_approved_change,
        )
        for e in result.scalars().all()
    ]


@router.get("/ip-investigation", response_model=list[IpInvestigationResponse])
async def list_observed_ips(db: AsyncSession = Depends(get_db), search: str | None = None) -> list[IpInvestigationResponse]:
    query = select(ObservedIpAddress).order_by(ObservedIpAddress.last_seen_at.desc())
    if search:
        query = query.where(ObservedIpAddress.ip_address.ilike(f"%{search}%"))
    result = await db.execute(query)
    ips = result.scalars().all()

    responses = []
    for ip in ips:
        login_count = (
            await db.execute(select(func.count()).select_from(LoginEvent).where(LoginEvent.source_ip == ip.ip_address))
        ).scalar_one()
        event_count = (
            await db.execute(select(func.count()).select_from(SecurityEvent).where(SecurityEvent.source_ip == ip.ip_address))
        ).scalar_one()
        responses.append(
            IpInvestigationResponse(
                ip_address=ip.ip_address,
                country=ip.country,
                city=ip.city,
                isp=ip.isp,
                asn=ip.asn,
                first_seen_at=ip.first_seen_at,
                last_seen_at=ip.last_seen_at,
                login_attempt_count=login_count,
                related_security_event_count=event_count,
            )
        )
    return responses


@router.get("/incidents", response_model=list[DowntimeIncidentResponse])
async def list_incidents(db: AsyncSession = Depends(get_db), open_only: bool = False) -> list[DowntimeIncidentResponse]:
    query = select(DowntimeIncident).order_by(DowntimeIncident.started_at.desc())
    if open_only:
        query = query.where(DowntimeIncident.resolved_at.is_(None))
    result = await db.execute(query)
    return [
        DowntimeIncidentResponse(
            id=i.id,
            target_type=i.target_type.value,
            target_id=i.target_id,
            started_at=i.started_at,
            resolved_at=i.resolved_at,
            cause=i.cause.value,
            detail=i.detail,
            acknowledged_at=i.acknowledged_at,
        )
        for i in result.scalars().all()
    ]
