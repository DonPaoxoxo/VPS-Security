from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AgentEnrollRequest(BaseModel):
    enrollment_token: str
    agent_version: str | None = None


class AgentEnrollResponse(BaseModel):
    agent_id: UUID
    server_id: UUID
    api_key: str  # shown once; never retrievable again


class HeartbeatRequest(BaseModel):
    agent_version: str | None = None
    operating_system: str | None = None
    cpu_pct: float | None = None
    ram_pct: float | None = None
    disk_pct: float | None = None
    load_average: float | None = None
    network_rx_bytes: int | None = None
    network_tx_bytes: int | None = None
    service_status: dict[str, str] | None = None
    aapanel_local_status: str | None = None  # running/stopped/not_installed, as observed by the agent locally


class HeartbeatResponse(BaseModel):
    received_at: datetime
    server_id: UUID


class DiscoveredVirtualHost(BaseModel):
    document_root: str
    web_server: str  # nginx/apache/openlitespeed/aapanel
    hostnames: list[str]
    configured_port: int | None = None
    ssl_available: bool = False
    redirect_target: str | None = None
    indicators: dict[str, bool] = {}
    """Read-only indicator flags gathered by the agent, e.g.
    {"has_wp_config": true, "has_wp_content_dir": true, "has_index_html_only": false}
    Classification itself happens server-side from these indicators."""


class DiscoverySubmitRequest(BaseModel):
    started_at: datetime
    finished_at: datetime
    virtual_hosts: list[DiscoveredVirtualHost]


class DiscoverySubmitResponse(BaseModel):
    discovery_run_id: UUID
    websites_found: int
    websites_new: int


class SecurityEventSubmit(BaseModel):
    event_type: str
    severity: str = "info"
    occurred_at: datetime
    source_ip: str | None = None
    account: str | None = None
    evidence: dict | None = None


class LoginEventSubmit(BaseModel):
    occurred_at: datetime
    was_successful: bool
    source_ip: str | None = None
    account: str | None = None
    auth_method: str | None = None


class FileIntegrityEventSubmit(BaseModel):
    file_path: str
    change_type: str
    detected_at: datetime
    previous_hash: str | None = None
    new_hash: str | None = None
    responsible_account: str | None = None
    responsible_process: str | None = None


class AgentEventsBatchSubmit(BaseModel):
    security_events: list[SecurityEventSubmit] = []
    login_events: list[LoginEventSubmit] = []
    file_integrity_events: list[FileIntegrityEventSubmit] = []
