from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db, require_csrf
from app.schemas.misc import AlertResponse
from ssc_core.models.alerting import Alert, AlertStatus

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


def _to_response(a: Alert) -> AlertResponse:
    return AlertResponse(
        id=a.id,
        alert_type=a.alert_type,
        severity=a.severity.value,
        status=a.status.value,
        server_id=a.server_id,
        website_id=a.website_id,
        title=a.title,
        detail=a.detail,
        triggered_at=a.triggered_at,
        acknowledged_at=a.acknowledged_at,
        resolved_at=a.resolved_at,
    )


@router.get("", response_model=list[AlertResponse])
async def list_alerts(db: AsyncSession = Depends(get_db), status_filter: str | None = None) -> list[AlertResponse]:
    query = select(Alert).order_by(Alert.triggered_at.desc())
    if status_filter:
        query = query.where(Alert.status == AlertStatus(status_filter))
    result = await db.execute(query)
    return [_to_response(a) for a in result.scalars().all()]


@router.post("/{alert_id}/acknowledge", dependencies=[Depends(require_csrf)])
async def acknowledge_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)) -> AlertResponse:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = AlertStatus.acknowledged
    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    return _to_response(alert)


@router.post("/{alert_id}/resolve", dependencies=[Depends(require_csrf)])
async def resolve_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)) -> AlertResponse:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = AlertStatus.resolved
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return _to_response(alert)
