from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ServerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    hostname_or_ip: str = Field(min_length=1, max_length=255)
    provider: str | None = None
    country: str | None = None
    has_aapanel: bool = False
    aapanel_endpoint_url: str | None = None
    aapanel_port: int | None = None
    group_id: UUID | None = None


class ServerUpdateRequest(BaseModel):
    name: str | None = None
    hostname_or_ip: str | None = None
    provider: str | None = None
    country: str | None = None
    group_id: UUID | None = None
    monitoring_status: str | None = None
    is_archived: bool | None = None


class ServerGroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ServerResponse(BaseModel):
    id: UUID
    name: str
    hostname_or_ip: str
    provider: str | None
    country: str | None
    operating_system: str | None
    group_id: UUID | None
    has_aapanel: bool
    monitoring_status: str
    is_archived: bool
    registered_at: datetime
    agent_status: str | None = None
    last_heartbeat_at: datetime | None = None
    aapanel_status: str | None = None
    cpu_pct: float | None = None
    ram_pct: float | None = None
    disk_pct: float | None = None

    class Config:
        from_attributes = True


class EnrollmentTokenResponse(BaseModel):
    server_id: UUID
    enrollment_token: str
    expires_at: datetime
    install_command: str
