from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db, require_csrf
from app.schemas.misc import TelegramSettingsRequest, TelegramSettingsResponse
from ssc_core.models.settings import ApplicationSetting

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(get_current_user)])

_TELEGRAM_KEY = "telegram"


@router.get("/telegram", response_model=TelegramSettingsResponse)
async def get_telegram_settings(db: AsyncSession = Depends(get_db)) -> TelegramSettingsResponse:
    result = await db.execute(select(ApplicationSetting).where(ApplicationSetting.key == _TELEGRAM_KEY))
    row = result.scalar_one_or_none()
    if row is None or not row.value.get("bot_token"):
        return TelegramSettingsResponse(configured=False)
    chat_id = row.value.get("chat_id", "")
    masked = f"***{chat_id[-4:]}" if len(chat_id) > 4 else "***"
    return TelegramSettingsResponse(configured=True, chat_id_masked=masked)


@router.put("/telegram", response_model=TelegramSettingsResponse, dependencies=[Depends(require_csrf)])
async def set_telegram_settings(
    payload: TelegramSettingsRequest, db: AsyncSession = Depends(get_db)
) -> TelegramSettingsResponse:
    """Stores Telegram credentials server-side only. They are never echoed
    back in full and never sent to the browser in subsequent reads."""
    value = {"bot_token": payload.bot_token, "chat_id": payload.chat_id}
    stmt = (
        insert(ApplicationSetting)
        .values(key=_TELEGRAM_KEY, value=value)
        .on_conflict_do_update(index_elements=[ApplicationSetting.key], set_={"value": value})
    )
    await db.execute(stmt)
    await db.commit()
    return await get_telegram_settings(db)
