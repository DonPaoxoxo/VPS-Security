from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from ssc_core.models.monitoring import PerformanceMetric

router = APIRouter(prefix="/performance", tags=["performance"], dependencies=[Depends(get_current_user)])


@router.get("/{server_id}")
async def get_server_performance(
    server_id: UUID, db: AsyncSession = Depends(get_db), hours: int = 24
) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(PerformanceMetric)
        .where(PerformanceMetric.server_id == server_id, PerformanceMetric.recorded_at >= since)
        .order_by(PerformanceMetric.recorded_at.asc())
    )
    return [
        {
            "recorded_at": m.recorded_at.isoformat(),
            "cpu_pct": m.cpu_pct,
            "ram_pct": m.ram_pct,
            "disk_pct": m.disk_pct,
            "load_average": m.load_average,
            "network_rx_bytes": m.network_rx_bytes,
            "network_tx_bytes": m.network_tx_bytes,
            "service_status": m.service_status,
        }
        for m in result.scalars().all()
    ]
