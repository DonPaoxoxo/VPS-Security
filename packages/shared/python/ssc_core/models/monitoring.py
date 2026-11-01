import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ssc_core.db import Base
from ssc_core.models.base import TimestampMixin, uuid_pk


class CheckTargetType(str, enum.Enum):
    server = "server"
    website = "website"
    aapanel = "aapanel"


class IncidentCause(str, enum.Enum):
    external_connection_failure = "external_connection_failure"
    agent_disconnected = "agent_disconnected"
    service_failure = "service_failure"
    unknown = "unknown"


class UptimeCheck(Base, TimestampMixin):
    """A single check result. target_type + target_id identify what was checked."""

    __tablename__ = "uptime_checks"

    id: Mapped[uuid.UUID] = uuid_pk()
    target_type: Mapped[CheckTargetType] = mapped_column(
        Enum(CheckTargetType, name="check_target_type"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_up: Mapped[bool] = mapped_column(nullable=False)
    response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class DowntimeIncident(Base, TimestampMixin):
    __tablename__ = "downtime_incidents"

    id: Mapped[uuid.UUID] = uuid_pk()
    target_type: Mapped[CheckTargetType] = mapped_column(
        Enum(CheckTargetType, name="check_target_type"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cause: Mapped[IncidentCause] = mapped_column(
        Enum(IncidentCause, name="incident_cause"), default=IncidentCause.unknown, nullable=False
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PerformanceMetric(Base, TimestampMixin):
    __tablename__ = "performance_metrics"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cpu_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ram_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    network_rx_bytes: Mapped[int | None] = mapped_column(nullable=True)
    network_tx_bytes: Mapped[int | None] = mapped_column(nullable=True)
    service_status: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
