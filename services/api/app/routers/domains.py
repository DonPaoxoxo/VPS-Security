from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_current_user, get_db, require_csrf
from app.schemas.websites import (
    EvidenceItem,
    WebsiteResponse,
    WebsiteReviewBatchRequest,
    WebsiteUpdateRequest,
)
from app.services.audit import record_audit
from ssc_core.models.server import Server
from ssc_core.models.user import User
from ssc_core.models.website import (
    DiscoveryStatus,
    MonitoringTarget,
    Website,
    WebsiteType,
)

router = APIRouter(prefix="/domains", tags=["domains"], dependencies=[Depends(get_current_user)])


def _to_response(website: Website) -> WebsiteResponse:
    return WebsiteResponse(
        id=website.id,
        server_id=website.server_id,
        server_name=website.server.name if website.server else None,
        document_root=website.document_root,
        web_server=website.web_server,
        website_type=website.website_type.value,
        classification_confidence=website.classification_confidence,
        discovery_status=website.discovery_status.value,
        ssl_available=website.ssl_available,
        configured_port=website.configured_port,
        redirect_target=website.redirect_target,
        last_discovered_at=website.last_discovered_at,
        monitoring_enabled=website.monitoring_enabled,
        domains=[{"id": d.id, "hostname": d.hostname, "is_primary": d.is_primary} for d in website.domains],
        evidence=[
            EvidenceItem(candidate_type=e.candidate_type.value, indicator=e.indicator, weight=e.weight)
            for e in website.evidence
        ],
    )


@router.get("", response_model=list[WebsiteResponse])
async def list_domains(
    db: AsyncSession = Depends(get_db),
    website_type: str | None = None,
    discovery_status: str | None = None,
    server_id: UUID | None = None,
) -> list[WebsiteResponse]:
    query = select(Website).options(
        selectinload(Website.server), selectinload(Website.domains), selectinload(Website.evidence)
    )
    if website_type:
        query = query.where(Website.website_type == WebsiteType(website_type))
    if discovery_status:
        query = query.where(Website.discovery_status == DiscoveryStatus(discovery_status))
    if server_id:
        query = query.where(Website.server_id == server_id)
    result = await db.execute(query.order_by(Website.last_discovered_at.desc()))
    return [_to_response(w) for w in result.scalars().all()]


@router.get("/pending-review", response_model=list[WebsiteResponse])
async def list_pending_review(server_id: UUID | None = None, db: AsyncSession = Depends(get_db)) -> list[WebsiteResponse]:
    """Add Server Wizard step 5: shows newly discovered websites awaiting approval/exclusion."""
    query = (
        select(Website)
        .options(selectinload(Website.server), selectinload(Website.domains), selectinload(Website.evidence))
        .where(Website.discovery_status == DiscoveryStatus.pending_review)
    )
    if server_id:
        query = query.where(Website.server_id == server_id)
    result = await db.execute(query)
    return [_to_response(w) for w in result.scalars().all()]


@router.post("/review", dependencies=[Depends(require_csrf)])
async def review_domains(
    payload: WebsiteReviewBatchRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    approved, excluded = 0, 0
    for decision in payload.decisions:
        result = await db.execute(select(Website).where(Website.id == decision.website_id))
        website = result.scalar_one_or_none()
        if website is None:
            continue
        if decision.decision == "approve":
            website.discovery_status = DiscoveryStatus.approved
            website.monitoring_enabled = decision.enable_monitoring
            if decision.website_type_override:
                website.website_type = WebsiteType(decision.website_type_override)
            if decision.enable_monitoring:
                existing_target = await db.execute(
                    select(MonitoringTarget).where(MonitoringTarget.website_id == website.id)
                )
                if existing_target.scalar_one_or_none() is None:
                    db.add(MonitoringTarget(website_id=website.id))
            approved += 1
        elif decision.decision == "exclude":
            website.discovery_status = DiscoveryStatus.excluded
            website.monitoring_enabled = False
            excluded += 1

    await record_audit(db, user_id=user.id, action="domains.review", detail={"approved": approved, "excluded": excluded})
    await db.commit()
    return {"approved": approved, "excluded": excluded}


@router.patch("/{website_id}", response_model=WebsiteResponse, dependencies=[Depends(require_csrf)])
async def update_website(
    website_id: UUID, payload: WebsiteUpdateRequest, db: AsyncSession = Depends(get_db)
) -> WebsiteResponse:
    result = await db.execute(
        select(Website)
        .options(selectinload(Website.server), selectinload(Website.domains), selectinload(Website.evidence))
        .where(Website.id == website_id)
    )
    website = result.scalar_one_or_none()
    if website is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Website not found")

    if payload.website_type_override:
        website.website_type = WebsiteType(payload.website_type_override)
    if payload.monitoring_enabled is not None:
        website.monitoring_enabled = payload.monitoring_enabled

    await db.commit()
    return _to_response(website)
