from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agents import DiscoveredVirtualHost, DiscoverySubmitRequest
from app.services.classification import classify
from ssc_core.models.website import (
    DomainClassificationEvidence,
    DomainDiscoveryRun,
    Website,
    WebsiteDomain,
)


async def process_discovery_submission(
    db: AsyncSession, server_id: UUID, payload: DiscoverySubmitRequest
) -> DomainDiscoveryRun:
    run = DomainDiscoveryRun(
        server_id=server_id,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        status="completed",
        websites_found=len(payload.virtual_hosts),
        websites_new=0,
        raw_payload=payload.model_dump(mode="json"),
    )
    db.add(run)

    existing_result = await db.execute(select(Website).where(Website.server_id == server_id))
    existing_by_root = {w.document_root: w for w in existing_result.scalars().all()}

    new_count = 0
    for vhost in payload.virtual_hosts:
        website = existing_by_root.get(vhost.document_root)
        is_new = website is None
        if website is None:
            classification = classify(vhost.indicators)
            website = Website(
                server_id=server_id,
                document_root=vhost.document_root,
                web_server=vhost.web_server,
                website_type=classification.website_type,
                classification_confidence=classification.confidence,
                ssl_available=vhost.ssl_available,
                configured_port=vhost.configured_port,
                redirect_target=vhost.redirect_target,
                last_discovered_at=datetime.now(timezone.utc),
            )
            db.add(website)
            await db.flush()  # assign website.id before attaching children
            for evidence_type, indicator, weight in classification.evidence:
                db.add(
                    DomainClassificationEvidence(
                        website_id=website.id,
                        candidate_type=evidence_type,
                        indicator=indicator,
                        weight=weight,
                    )
                )
            new_count += 1
        else:
            # Re-discovery: refresh observable attributes but never delete the
            # record, and never downgrade a reviewed/approved website silently.
            website.web_server = vhost.web_server
            website.ssl_available = vhost.ssl_available
            website.configured_port = vhost.configured_port
            website.redirect_target = vhost.redirect_target
            website.last_discovered_at = datetime.now(timezone.utc)

        await _sync_domains(db, website, vhost)

    run.websites_new = new_count
    await db.flush()
    return run


async def _sync_domains(db: AsyncSession, website: Website, vhost: DiscoveredVirtualHost) -> None:
    existing_result = await db.execute(select(WebsiteDomain).where(WebsiteDomain.website_id == website.id))
    existing = {d.hostname: d for d in existing_result.scalars().all()}

    for idx, hostname in enumerate(vhost.hostnames):
        if hostname in existing:
            continue
        db.add(WebsiteDomain(website_id=website.id, hostname=hostname, is_primary=(idx == 0)))
