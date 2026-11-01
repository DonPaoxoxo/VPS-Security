import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ssc_core.db import Base
from ssc_core.models.base import TimestampMixin, uuid_pk


class ApplicationSetting(Base, TimestampMixin):
    """Generic singleton key/value settings store (Telegram config, retention
    policy overrides, etc.)."""

    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class MaintenanceWindow(Base, TimestampMixin):
    __tablename__ = "maintenance_windows"

    id: Mapped[uuid.UUID] = uuid_pk()
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)  # server/website/global
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suppress_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ApprovedChange(Base, TimestampMixin):
    """A manually recorded deployment/maintenance change used to suppress
    false-positive file-integrity alerts for a known window."""

    __tablename__ = "approved_changes"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
