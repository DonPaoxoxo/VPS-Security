import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ssc_core.db import Base
from ssc_core.models.base import TimestampMixin, uuid_pk


class AgentStatus(str, enum.Enum):
    pending = "pending"
    connected = "connected"
    disconnected = "disconnected"
    never_connected = "never_connected"


class AapanelStatus(str, enum.Enum):
    healthy = "healthy"
    unreachable = "unreachable"
    service_stopped = "service_stopped"
    access_restricted = "access_restricted"
    degraded = "degraded"
    unknown = "unknown"


class ServerGroup(Base, TimestampMixin):
    __tablename__ = "server_groups"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    servers: Mapped[list["Server"]] = relationship(back_populates="group")


class Server(Base, TimestampMixin):
    __tablename__ = "servers"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    hostname_or_ip: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    operating_system: Mapped[str | None] = mapped_column(String(120), nullable=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("server_groups.id", ondelete="SET NULL"), nullable=True
    )

    has_aapanel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    monitoring_status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    group: Mapped[ServerGroup | None] = relationship(back_populates="servers")
    agent: Mapped["MonitoringAgent | None"] = relationship(back_populates="server", uselist=False)
    aapanel_instance: Mapped["AapanelInstance | None"] = relationship(
        back_populates="server", uselist=False
    )


class AgentEnrollmentToken(Base, TimestampMixin):
    """Short-lived, single-use token used to bootstrap a new agent's credentials."""

    __tablename__ = "agent_enrollment_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MonitoringAgent(Base, TimestampMixin):
    """A single, independently revocable credential for one server's agent."""

    __tablename__ = "monitoring_agents"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    api_key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, name="agent_status"), default=AgentStatus.pending, nullable=False
    )
    agent_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reported_os: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_reported_cpu_pct: Mapped[float | None] = mapped_column(nullable=True)
    last_reported_ram_pct: Mapped[float | None] = mapped_column(nullable=True)
    last_reported_disk_pct: Mapped[float | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    server: Mapped[Server] = relationship(back_populates="agent")


class AapanelInstance(Base, TimestampMixin):
    __tablename__ = "aapanel_instances"

    id: Mapped[uuid.UUID] = uuid_pk()
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    endpoint_url: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=8888)
    status: Mapped[AapanelStatus] = mapped_column(
        Enum(AapanelStatus, name="aapanel_status"), default=AapanelStatus.unknown, nullable=False
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_agent_reported_local_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    """running / stopped / not_installed — as observed directly on the host by
    the agent, independent of whether the central hub can reach the endpoint
    over the network. Used to tell a stopped service apart from a firewall or
    IP-allowlist restriction."""

    server: Mapped[Server] = relationship(back_populates="aapanel_instance")
