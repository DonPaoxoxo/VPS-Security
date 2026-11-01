from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OverviewResponse(BaseModel):
    total_servers: int
    online_servers: int
    offline_servers: int
    healthy_aapanel: int
    unreachable_aapanel: int
    total_domains: int
    wordpress_sites: int
    static_sites: int
    other_sites: int
    active_security_alerts: int
    file_modification_alerts: int
    failed_ssh_attempts_24h: int


class AapanelInstanceResponse(BaseModel):
    id: UUID
    server_id: UUID
    server_name: str | None = None
    endpoint_url: str
    port: int
    status: str
    last_checked_at: datetime | None
    last_status_detail: str | None

    class Config:
        from_attributes = True


class SecurityEventResponse(BaseModel):
    id: UUID
    server_id: UUID
    server_name: str | None = None
    event_type: str
    severity: str
    occurred_at: datetime
    source_ip: str | None
    account: str | None
    evidence: dict | None
    investigation_status: str

    class Config:
        from_attributes = True


class LoginEventResponse(BaseModel):
    id: UUID
    server_id: UUID
    server_name: str | None = None
    occurred_at: datetime
    was_successful: bool
    source_ip: str | None
    account: str | None
    auth_method: str | None

    class Config:
        from_attributes = True


class FileIntegrityEventResponse(BaseModel):
    id: UUID
    server_id: UUID
    server_name: str | None = None
    file_path: str
    change_type: str
    detected_at: datetime
    previous_hash: str | None
    new_hash: str | None
    responsible_account: str | None
    responsible_process: str | None
    is_approved_change: bool

    class Config:
        from_attributes = True


class IpInvestigationResponse(BaseModel):
    ip_address: str
    country: str | None
    city: str | None
    isp: str | None
    asn: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    login_attempt_count: int
    related_security_event_count: int


class AlertResponse(BaseModel):
    id: UUID
    alert_type: str
    severity: str
    status: str
    server_id: UUID | None
    website_id: UUID | None
    title: str
    detail: str | None
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None

    class Config:
        from_attributes = True


class DowntimeIncidentResponse(BaseModel):
    id: UUID
    target_type: str
    target_id: UUID
    started_at: datetime
    resolved_at: datetime | None
    cause: str
    detail: str | None
    acknowledged_at: datetime | None

    class Config:
        from_attributes = True


class TelegramSettingsRequest(BaseModel):
    bot_token: str | None = None
    chat_id: str | None = None


class TelegramSettingsResponse(BaseModel):
    configured: bool
    chat_id_masked: str | None = None
