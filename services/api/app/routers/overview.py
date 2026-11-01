from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.schemas.misc import OverviewResponse
from ssc_core.models.alerting import Alert, AlertStatus
from ssc_core.models.security import FileIntegrityEvent, LoginEvent
from ssc_core.models.server import AapanelInstance, AapanelStatus, AgentStatus, MonitoringAgent, Server
from ssc_core.models.website import DiscoveryStatus, Website, WebsiteType

router = APIRouter(prefix="/overview", tags=["overview"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=OverviewResponse)
async def get_overview(db: AsyncSession = Depends(get_db)) -> OverviewResponse:
    total_servers = (
        await db.execute(select(func.count()).select_from(Server).where(Server.is_archived.is_(False)))
    ).scalar_one()

    online_servers = (
        await db.execute(
            select(func.count())
            .select_from(MonitoringAgent)
            .join(Server, Server.id == MonitoringAgent.server_id)
            .where(MonitoringAgent.status == AgentStatus.connected, Server.is_archived.is_(False))
        )
    ).scalar_one()

    healthy_aapanel = (
        await db.execute(select(func.count()).select_from(AapanelInstance).where(AapanelInstance.status == AapanelStatus.healthy))
    ).scalar_one()
    unreachable_aapanel = (
        await db.execute(
            select(func.count())
            .select_from(AapanelInstance)
            .where(AapanelInstance.status.in_([AapanelStatus.unreachable, AapanelStatus.degraded, AapanelStatus.service_stopped]))
        )
    ).scalar_one()

    approved_filter = Website.discovery_status == DiscoveryStatus.approved
    total_domains = (await db.execute(select(func.count()).select_from(Website).where(approved_filter))).scalar_one()
    wordpress_sites = (
        await db.execute(select(func.count()).select_from(Website).where(approved_filter, Website.website_type == WebsiteType.wordpress))
    ).scalar_one()
    static_sites = (
        await db.execute(select(func.count()).select_from(Website).where(approved_filter, Website.website_type == WebsiteType.static))
    ).scalar_one()
    other_sites = (
        await db.execute(
            select(func.count())
            .select_from(Website)
            .where(approved_filter, Website.website_type.in_([WebsiteType.other, WebsiteType.unknown]))
        )
    ).scalar_one()

    active_security_alerts = (
        await db.execute(select(func.count()).select_from(Alert).where(Alert.status != AlertStatus.resolved))
    ).scalar_one()

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    file_modification_alerts = (
        await db.execute(
            select(func.count())
            .select_from(FileIntegrityEvent)
            .where(FileIntegrityEvent.detected_at >= since_24h, FileIntegrityEvent.is_approved_change.is_(False))
        )
    ).scalar_one()
    failed_ssh_attempts_24h = (
        await db.execute(
            select(func.count())
            .select_from(LoginEvent)
            .where(LoginEvent.occurred_at >= since_24h, LoginEvent.was_successful.is_(False))
        )
    ).scalar_one()

    return OverviewResponse(
        total_servers=total_servers,
        online_servers=online_servers,
        offline_servers=max(total_servers - online_servers, 0),
        healthy_aapanel=healthy_aapanel,
        unreachable_aapanel=unreachable_aapanel,
        total_domains=total_domains,
        wordpress_sites=wordpress_sites,
        static_sites=static_sites,
        other_sites=other_sites,
        active_security_alerts=active_security_alerts,
        file_modification_alerts=file_modification_alerts,
        failed_ssh_attempts_24h=failed_ssh_attempts_24h,
    )
