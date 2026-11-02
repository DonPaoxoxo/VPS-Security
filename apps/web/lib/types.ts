export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  totp_enabled: boolean;
  csrf_token: string;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  totp_enabled: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ServerSummary {
  id: string;
  name: string;
  hostname_or_ip: string;
  provider: string | null;
  country: string | null;
  operating_system: string | null;
  group_id: string | null;
  has_aapanel: boolean;
  monitoring_status: string;
  is_archived: boolean;
  registered_at: string;
  agent_status: "pending" | "connected" | "disconnected" | "never_connected" | null;
  last_heartbeat_at: string | null;
  aapanel_status: string | null;
  cpu_pct: number | null;
  ram_pct: number | null;
  disk_pct: number | null;
}

export interface EnrollmentToken {
  server_id: string;
  enrollment_token: string;
  expires_at: string;
  install_command: string;
}

export interface WebsiteDomain {
  id: string;
  hostname: string;
  is_primary: boolean;
}

export interface EvidenceItem {
  candidate_type: string;
  indicator: string;
  weight: number;
}

export interface Website {
  id: string;
  server_id: string;
  server_name: string | null;
  document_root: string;
  web_server: string | null;
  website_type: "wordpress" | "static" | "other" | "unknown";
  classification_confidence: number;
  discovery_status: "pending_review" | "approved" | "excluded";
  ssl_available: boolean;
  configured_port: number | null;
  redirect_target: string | null;
  last_discovered_at: string;
  monitoring_enabled: boolean;
  domains: WebsiteDomain[];
  evidence: EvidenceItem[];
}

export interface OverviewStats {
  total_servers: number;
  online_servers: number;
  offline_servers: number;
  healthy_aapanel: number;
  unreachable_aapanel: number;
  total_domains: number;
  wordpress_sites: number;
  static_sites: number;
  other_sites: number;
  active_security_alerts: number;
  file_modification_alerts: number;
  failed_ssh_attempts_24h: number;
}

export interface AapanelInstance {
  id: string;
  server_id: string;
  server_name: string | null;
  endpoint_url: string;
  port: number;
  status: "healthy" | "unreachable" | "service_stopped" | "access_restricted" | "degraded" | "unknown";
  last_checked_at: string | null;
  last_status_detail: string | null;
}

export interface SecurityEvent {
  id: string;
  server_id: string;
  server_name: string | null;
  event_type: string;
  severity: "info" | "warning" | "critical";
  occurred_at: string;
  source_ip: string | null;
  account: string | null;
  evidence: Record<string, unknown> | null;
  investigation_status: "suspected" | "confirmed" | "unknown" | "dismissed";
}

export interface LoginEvent {
  id: string;
  server_id: string;
  server_name: string | null;
  occurred_at: string;
  was_successful: boolean;
  source_ip: string | null;
  account: string | null;
  auth_method: string | null;
}

export interface FileIntegrityEvent {
  id: string;
  server_id: string;
  server_name: string | null;
  file_path: string;
  change_type: string;
  detected_at: string;
  previous_hash: string | null;
  new_hash: string | null;
  responsible_account: string | null;
  responsible_process: string | null;
  is_approved_change: boolean;
}

export interface IpInvestigation {
  ip_address: string;
  country: string | null;
  city: string | null;
  isp: string | null;
  asn: string | null;
  first_seen_at: string;
  last_seen_at: string;
  login_attempt_count: number;
  related_security_event_count: number;
}

export interface Alert {
  id: string;
  alert_type: string;
  severity: "info" | "warning" | "critical";
  status: "open" | "acknowledged" | "resolved";
  server_id: string | null;
  website_id: string | null;
  title: string;
  detail: string | null;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface DowntimeIncident {
  id: string;
  target_type: "server" | "website" | "aapanel";
  target_id: string;
  started_at: string;
  resolved_at: string | null;
  cause: "external_connection_failure" | "agent_disconnected" | "service_failure" | "unknown";
  detail: string | null;
  acknowledged_at: string | null;
}
