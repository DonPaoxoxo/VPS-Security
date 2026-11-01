import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ssc_core.db import Base
from ssc_core.models.base import TimestampMixin, uuid_pk


class WebsiteType(str, enum.Enum):
    wordpress = "wordpress"
    static = "static"
    other = "other"
    unknown = "unknown"


class DiscoveryStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    excluded = "excluded"


class Website(Base, TimestampMixin):
    """A single hosted website: one document root / virtual host on a server.
    Domain aliases live in WebsiteDomain."""

    __tablename__ = "websites"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_root: Mapped[str] = mapped_column(String(500), nullable=False)
    web_server: Mapped[str | None] = mapped_column(String(40), nullable=True)  # nginx/apache/ols
    website_type: Mapped[WebsiteType] = mapped_column(
        Enum(WebsiteType, name="website_type"), default=WebsiteType.unknown, nullable=False
    )
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discovery_status: Mapped[DiscoveryStatus] = mapped_column(
        Enum(DiscoveryStatus, name="discovery_status"),
        default=DiscoveryStatus.pending_review,
        nullable=False,
    )
    ssl_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    configured_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redirect_target: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    domains: Mapped[list["WebsiteDomain"]] = relationship(back_populates="website", cascade="all, delete-orphan")
    evidence: Mapped[list["DomainClassificationEvidence"]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )
    monitoring_target: Mapped["MonitoringTarget | None"] = relationship(
        back_populates="website", uselist=False
    )
    server: Mapped["Server"] = relationship()  # one-directional; Server does not track its websites list


class WebsiteDomain(Base, TimestampMixin):
    """A single hostname (primary domain, alias, subdomain, or www-variant)
    pointing at a Website's virtual host."""

    __tablename__ = "website_domains"

    id: Mapped[uuid.UUID] = uuid_pk()
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    website: Mapped[Website] = relationship(back_populates="domains")


class DomainDiscoveryRun(Base, TimestampMixin):
    __tablename__ = "domain_discovery_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False)
    websites_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    websites_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class DomainClassificationEvidence(Base, TimestampMixin):
    __tablename__ = "domain_classification_evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_type: Mapped[WebsiteType] = mapped_column(Enum(WebsiteType, name="website_type"), nullable=False)
    indicator: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)

    website: Mapped[Website] = relationship(back_populates="evidence")


class MonitoringTarget(Base, TimestampMixin):
    """Active uptime-check configuration for an approved website."""

    __tablename__ = "monitoring_targets"

    id: Mapped[uuid.UUID] = uuid_pk()
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    check_interval_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    expected_status_codes: Mapped[str] = mapped_column(String(80), default="200-399", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_state: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)

    website: Mapped[Website] = relationship(back_populates="monitoring_target")
