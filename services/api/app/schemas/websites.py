from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    candidate_type: str
    indicator: str
    weight: float


class WebsiteDomainResponse(BaseModel):
    id: UUID
    hostname: str
    is_primary: bool

    class Config:
        from_attributes = True


class WebsiteResponse(BaseModel):
    id: UUID
    server_id: UUID
    server_name: str | None = None
    document_root: str
    web_server: str | None
    website_type: str
    classification_confidence: float
    discovery_status: str
    ssl_available: bool
    configured_port: int | None
    redirect_target: str | None
    last_discovered_at: datetime
    monitoring_enabled: bool
    domains: list[WebsiteDomainResponse] = []
    evidence: list[EvidenceItem] = []
    http_status: int | None = None
    ssl_expires_at: datetime | None = None
    last_checked_at: datetime | None = None

    class Config:
        from_attributes = True


class WebsiteReviewDecision(BaseModel):
    website_id: UUID
    decision: str  # approve/exclude
    website_type_override: str | None = None
    enable_monitoring: bool = True


class WebsiteReviewBatchRequest(BaseModel):
    decisions: list[WebsiteReviewDecision]


class WebsiteUpdateRequest(BaseModel):
    website_type_override: str | None = None
    monitoring_enabled: bool | None = None
