import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ssc_core.db import Base
from ssc_core.models.base import TimestampMixin, uuid_pk


class SeverityLevel(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class InvestigationStatus(str, enum.Enum):
    suspected = "suspected"
    confirmed = "confirmed"
    unknown = "unknown"
    dismissed = "dismissed"


class SecurityEvent(Base, TimestampMixin):
    __tablename__ = "security_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel, name="severity_level"), default=SeverityLevel.info, nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    account: Mapped[str | None] = mapped_column(String(120), nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    investigation_status: Mapped[InvestigationStatus] = mapped_column(
        Enum(InvestigationStatus, name="investigation_status"),
        default=InvestigationStatus.unknown,
        nullable=False,
    )

    server: Mapped["Server"] = relationship()


class LoginEvent(Base, TimestampMixin):
    __tablename__ = "login_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    was_successful: Mapped[bool] = mapped_column(nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    account: Mapped[str | None] = mapped_column(String(120), nullable=True)
    auth_method: Mapped[str | None] = mapped_column(String(40), nullable=True)

    server: Mapped["Server"] = relationship()


class FileIntegrityEvent(Base, TimestampMixin):
    __tablename__ = "file_integrity_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(40), nullable=False)  # created/modified/deleted/perm/owner
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    previous_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    new_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    responsible_account: Mapped[str | None] = mapped_column(String(120), nullable=True)
    responsible_process: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_approved_change: Mapped[bool] = mapped_column(default=False, nullable=False)

    server: Mapped["Server"] = relationship()


class ObservedIpAddress(Base, TimestampMixin):
    __tablename__ = "observed_ip_addresses"

    id: Mapped[uuid.UUID] = uuid_pk()
    ip_address: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    isp: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asn: Mapped[str | None] = mapped_column(String(40), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
