from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from ssc_core.models.user import AuditLog

router = APIRouter(prefix="/audit-logs", tags=["audit"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_audit_logs(db: AsyncSession = Depends(get_db), limit: int = 200) -> list[dict]:
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    return [
        {
            "id": str(a.id),
            "action": a.action,
            "resource_type": a.resource_type,
            "resource_id": a.resource_id,
            "detail": a.detail,
            "ip_address": a.ip_address,
            "created_at": a.created_at.isoformat(),
        }
        for a in result.scalars().all()
    ]
