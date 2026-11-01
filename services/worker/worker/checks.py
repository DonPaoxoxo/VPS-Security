"""Background monitoring jobs: website uptime, server reachability, and
aaPanel health. Each job is independent and short-lived so a single slow
target cannot stall the whole scheduler."""

import asyncio
import logging
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ssc_core.config import get_settings
from ssc_core.models.alerting import Alert, AlertStatus
from ssc_core.models.monitoring import CheckTargetType, DowntimeIncident, IncidentCause, PerformanceMetric, UptimeCheck
from ssc_core.models.security import SeverityLevel
from ssc_core.models.server import AapanelInstance, AapanelStatus, AgentStatus, MonitoringAgent, Server
from ssc_core.models.website import DiscoveryStatus, MonitoringTarget, Website
from ssc_core.net_safety import is_safe_monitoring_target
from ssc_core.notify import format_alert_message, send_telegram_message

logger = logging.getLogger("ssc.worker")
settings = get_settings()


async def _tcp_reachable(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, socket.create_connection, (host, port), timeout)
        conn = await asyncio.wait_for(fut, timeout=timeout + 1)
        conn.close()
        return True
    except Exception:
        return False


async def _get_or_open_incident(
    db: AsyncSession, target_type: CheckTargetType, target_id: UUID, cause: IncidentCause, detail: str
) -> DowntimeIncident | None:
    existing = await db.execute(
        select(DowntimeIncident).where(
            DowntimeIncident.target_type == target_type,
            DowntimeIncident.target_id == target_id,
            DowntimeIncident.resolved_at.is_(None),
        )
    )
    incident = existing.scalar_one_or_none()
    if incident is not None:
        incident.cause = cause
        incident.detail = detail
        return None  # already open; no new notification
    incident = DowntimeIncident(
        target_type=target_type, target_id=target_id, started_at=datetime.now(timezone.utc), cause=cause, detail=detail
    )
    db.add(incident)
    await db.flush()
    return incident


async def _close_incident(db: AsyncSession, target_type: CheckTargetType, target_id: UUID) -> DowntimeIncident | None:
    existing = await db.execute(
        select(DowntimeIncident).where(
            DowntimeIncident.target_type == target_type,
            DowntimeIncident.target_id == target_id,
            DowntimeIncident.resolved_at.is_(None),
        )
    )
    incident = existing.scalar_one_or_none()
    if incident is None:
        return None
    incident.resolved_at = datetime.now(timezone.utc)
    return incident


async def check_website_uptime(db: AsyncSession) -> None:
    result = await db.execute(
        select(MonitoringTarget)
        .join(Website, Website.id == MonitoringTarget.website_id)
        .options(selectinload(MonitoringTarget.website).selectinload(Website.domains))
        .where(MonitoringTarget.is_enabled.is_(True), Website.discovery_status == DiscoveryStatus.approved)
    )
    targets = result.scalars().all()

    # Redirects are not auto-followed: each hop would need its own SSRF check
    # (an attacker-influenced vhost could 302 to an internal address), and a
    # redirect to an unexpected destination is itself worth surfacing rather
    # than silently following.
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, verify=True) as client:
        for target in targets:
            website = target.website
            primary_domain = next((d.hostname for d in website.domains if d.is_primary), None) or (
                website.domains[0].hostname if website.domains else None
            )
            if not primary_domain:
                continue

            is_safe, reason = is_safe_monitoring_target(primary_domain)
            if not is_safe:
                logger.warning("Skipping uptime check for %s: %s", primary_domain, reason)
                db.add(
                    UptimeCheck(
                        target_type=CheckTargetType.website,
                        target_id=website.id,
                        checked_at=datetime.now(timezone.utc),
                        is_up=False,
                        detail=f"Monitoring skipped: {reason}",
                    )
                )
                continue

            scheme = "https" if website.ssl_available else "http"
            url = f"{scheme}://{primary_domain}/"
            is_up = False
            status_code = None
            response_ms = None
            detail = ""
            try:
                start = datetime.now(timezone.utc)
                resp = await client.get(url)
                response_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                status_code = resp.status_code
                is_up = 200 <= resp.status_code < 400
                if 300 <= resp.status_code < 400:
                    detail = f"Redirects to {resp.headers.get('location', 'unknown location')}"
                elif resp.status_code >= 500:
                    detail = f"HTTP {resp.status_code} from origin"
            except httpx.HTTPError as exc:
                detail = f"Request failed: {exc}"

            db.add(
                UptimeCheck(
                    target_type=CheckTargetType.website,
                    target_id=website.id,
                    checked_at=datetime.now(timezone.utc),
                    is_up=is_up,
                    response_time_ms=response_ms,
                    status_code=status_code,
                    detail=detail or None,
                )
            )

            if is_up:
                target.consecutive_failures = 0
                target.consecutive_successes += 1
                if (
                    target.current_state == "down"
                    and target.consecutive_successes >= settings.consecutive_successes_for_recovery
                ):
                    target.current_state = "up"
                    incident = await _close_incident(db, CheckTargetType.website, website.id)
                    if incident:
                        await _resolve_alerts(db, alert_type="website_offline", server_id=None, website_id=website.id)
                        await _notify(
                            alert_type="website_recovered",
                            severity="info",
                            server_name=None,
                            domain=primary_domain,
                            detail=f"{primary_domain} recovered after {incident.started_at.isoformat()}",
                        )
                elif target.current_state != "down":
                    target.current_state = "up"
            else:
                target.consecutive_successes = 0
                target.consecutive_failures += 1
                if (
                    target.current_state != "down"
                    and target.consecutive_failures >= settings.consecutive_failures_for_down
                ):
                    target.current_state = "down"
                    incident = await _get_or_open_incident(
                        db,
                        CheckTargetType.website,
                        website.id,
                        IncidentCause.service_failure if status_code else IncidentCause.unknown,
                        detail,
                    )
                    if incident:
                        await _open_alert(
                            db,
                            alert_type="website_offline",
                            severity="critical",
                            server_id=None,
                            website_id=website.id,
                            title=f"{primary_domain} is offline",
                            detail=detail or "Website failed consecutive health checks",
                        )
                        await _notify(
                            alert_type="website_offline",
                            severity="critical",
                            server_name=None,
                            domain=primary_domain,
                            detail=detail or "Website failed consecutive health checks",
                        )

    await db.commit()


async def check_server_connectivity(db: AsyncSession) -> None:
    result = await db.execute(
        select(Server, MonitoringAgent)
        .join(MonitoringAgent, MonitoringAgent.server_id == Server.id, isouter=True)
        .where(Server.is_archived.is_(False))
    )
    rows = result.all()
    stale_after = timedelta(seconds=settings.agent_heartbeat_stale_seconds)

    for server, agent in rows:
        if agent is None:
            continue  # no agent enrolled yet — nothing to check

        is_stale = agent.last_heartbeat_at is None or (
            datetime.now(timezone.utc) - agent.last_heartbeat_at > stale_after
        )

        if not is_stale:
            if agent.status != AgentStatus.connected:
                agent.status = AgentStatus.connected
            db.add(
                UptimeCheck(
                    target_type=CheckTargetType.server,
                    target_id=server.id,
                    checked_at=datetime.now(timezone.utc),
                    is_up=True,
                )
            )
            incident = await _close_incident(db, CheckTargetType.server, server.id)
            if incident:
                await _resolve_alerts(db, alert_type="server_offline", server_id=server.id, website_id=None)
                await _notify(
                    alert_type="server_recovered", severity="info", server_name=server.name, domain=None,
                    detail=f"{server.name} agent reconnected",
                )
            continue

        # Agent heartbeat is stale. A failed outbound TCP probe to the host
        # adds evidence but is never treated as definitive on its own.
        host = server.hostname_or_ip
        tcp_ok = await _tcp_reachable(host, 22) or await _tcp_reachable(host, 443) or await _tcp_reachable(host, 80)
        cause = IncidentCause.external_connection_failure if not tcp_ok else IncidentCause.agent_disconnected
        detail = (
            f"No heartbeat since {agent.last_heartbeat_at.isoformat() if agent.last_heartbeat_at else 'never'}; "
            f"outbound TCP probe {'succeeded' if tcp_ok else 'failed'}"
        )

        agent.status = AgentStatus.disconnected
        db.add(
            UptimeCheck(
                target_type=CheckTargetType.server,
                target_id=server.id,
                checked_at=datetime.now(timezone.utc),
                is_up=False,
                detail=detail,
            )
        )
        incident = await _get_or_open_incident(db, CheckTargetType.server, server.id, cause, detail)
        if incident:
            await _open_alert(
                db,
                alert_type="server_offline",
                severity="critical",
                server_id=server.id,
                website_id=None,
                title=f"{server.name} is unreachable",
                detail=detail,
            )
            await _notify(
                alert_type="server_offline", severity="critical", server_name=server.name, domain=None, detail=detail
            )

    await db.commit()


async def check_aapanel_health(db: AsyncSession) -> None:
    result = await db.execute(select(AapanelInstance).options(selectinload(AapanelInstance.server)))
    instances = result.scalars().all()

    for instance in instances:
        host = urlparse(instance.endpoint_url).hostname or instance.endpoint_url
        tcp_ok = await _tcp_reachable(host, instance.port)
        local_status = instance.last_agent_reported_local_status

        previous_status = instance.status
        if local_status == "stopped":
            instance.status = AapanelStatus.service_stopped
            instance.last_status_detail = "Agent reports the local aaPanel service is stopped."
        elif tcp_ok:
            instance.status = AapanelStatus.healthy
            instance.last_status_detail = "Endpoint reachable over TCP."
        elif local_status == "running":
            # Agent sees it running locally, but the hub can't reach the
            # endpoint — most likely firewall/IP allowlist, not a stopped service.
            instance.status = AapanelStatus.access_restricted
            instance.last_status_detail = (
                "Agent reports the service is running locally, but the endpoint is not reachable "
                "from the monitoring hub — likely a firewall or IP allowlist restriction."
            )
        elif local_status is None:
            instance.status = AapanelStatus.unknown
            instance.last_status_detail = "No agent-reported local status available yet, and the endpoint is unreachable."
        else:
            instance.status = AapanelStatus.unreachable
            instance.last_status_detail = "Endpoint unreachable from the monitoring hub."

        instance.last_checked_at = datetime.now(timezone.utc)

        if previous_status == AapanelStatus.healthy and instance.status != AapanelStatus.healthy:
            await _open_alert(
                db,
                alert_type="aapanel_unreachable",
                severity="warning",
                server_id=instance.server_id,
                website_id=None,
                title=f"aaPanel unreachable on {instance.server.name if instance.server else instance.server_id}",
                detail=instance.last_status_detail or "",
            )
            await _notify(
                alert_type="aapanel_unreachable",
                severity="warning",
                server_name=instance.server.name if instance.server else None,
                domain=None,
                detail=instance.last_status_detail,
            )
        elif previous_status != AapanelStatus.healthy and instance.status == AapanelStatus.healthy:
            await _resolve_alerts(db, alert_type="aapanel_unreachable", server_id=instance.server_id, website_id=None)
            await _notify(
                alert_type="aapanel_recovered",
                severity="info",
                server_name=instance.server.name if instance.server else None,
                domain=None,
                detail="aaPanel endpoint reachable again.",
            )

    await db.commit()


async def _open_alert(
    db: AsyncSession, *, alert_type: str, severity: str, server_id: UUID | None, website_id: UUID | None, title: str, detail: str
) -> None:
    db.add(
        Alert(
            alert_type=alert_type,
            severity=SeverityLevel(severity),
            status=AlertStatus.open,
            server_id=server_id,
            website_id=website_id,
            title=title,
            detail=detail,
            triggered_at=datetime.now(timezone.utc),
        )
    )


async def _resolve_alerts(db: AsyncSession, *, alert_type: str, server_id: UUID | None, website_id: UUID | None) -> None:
    query = select(Alert).where(Alert.alert_type == alert_type, Alert.status != AlertStatus.resolved)
    if server_id is not None:
        query = query.where(Alert.server_id == server_id)
    if website_id is not None:
        query = query.where(Alert.website_id == website_id)
    result = await db.execute(query)
    for alert in result.scalars().all():
        alert.status = AlertStatus.resolved
        alert.resolved_at = datetime.now(timezone.utc)


async def _notify(*, alert_type: str, severity: str, server_name: str | None, domain: str | None, detail: str) -> None:
    message = format_alert_message(
        alert_type=alert_type,
        severity=severity,
        server_name=server_name,
        domain=domain,
        detail=detail,
        timestamp=datetime.now(timezone.utc).isoformat(),
        incident_url=None,
    )
    success, error = await send_telegram_message(message)
    if not success and error:
        logger.info("Telegram notification skipped/failed: %s", error)


async def purge_old_data(db: AsyncSession) -> None:
    """Enforces the configurable retention windows (ssc_core.config) — without
    this, performance_metrics and uptime_checks grow forever. Downtime
    incidents and alerts are left alone; they're small in volume and valuable
    as long-term history."""
    now = datetime.now(timezone.utc)

    metrics_cutoff = now - timedelta(days=settings.performance_metrics_retention_days)
    result = await db.execute(delete(PerformanceMetric).where(PerformanceMetric.recorded_at < metrics_cutoff))
    metrics_deleted = result.rowcount or 0

    uptime_cutoff = now - timedelta(days=settings.uptime_history_retention_days)
    result = await db.execute(delete(UptimeCheck).where(UptimeCheck.checked_at < uptime_cutoff))
    uptime_deleted = result.rowcount or 0

    await db.commit()
    if metrics_deleted or uptime_deleted:
        logger.info(
            "Retention purge: removed %s performance_metrics rows older than %sd, %s uptime_checks rows older than %sd",
            metrics_deleted,
            settings.performance_metrics_retention_days,
            uptime_deleted,
            settings.uptime_history_retention_days,
        )
