from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_current_user, get_db
from app.schemas.misc import AapanelInstanceResponse
from ssc_core.models.server import AapanelInstance

router = APIRouter(prefix="/aapanel", tags=["aapanel"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AapanelInstanceResponse])
async def list_aapanel_instances(db: AsyncSession = Depends(get_db)) -> list[AapanelInstanceResponse]:
    result = await db.execute(select(AapanelInstance).options(selectinload(AapanelInstance.server)))
    instances = result.scalars().all()
    return [
        AapanelInstanceResponse(
            id=i.id,
            server_id=i.server_id,
            server_name=i.server.name if i.server else None,
            endpoint_url=i.endpoint_url,
            port=i.port,
            status=i.status.value,
            last_checked_at=i.last_checked_at,
            last_status_detail=i.last_status_detail,
        )
        for i in instances
    ]


@router.get("/{instance_id}", response_model=AapanelInstanceResponse)
async def get_aapanel_instance(instance_id: UUID, db: AsyncSession = Depends(get_db)) -> AapanelInstanceResponse:
    result = await db.execute(
        select(AapanelInstance).options(selectinload(AapanelInstance.server)).where(AapanelInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="aaPanel instance not found")
    return AapanelInstanceResponse(
        id=instance.id,
        server_id=instance.server_id,
        server_name=instance.server.name if instance.server else None,
        endpoint_url=instance.endpoint_url,
        port=instance.port,
        status=instance.status.value,
        last_checked_at=instance.last_checked_at,
        last_status_detail=instance.last_status_detail,
    )
