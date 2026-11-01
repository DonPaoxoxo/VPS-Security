#!/usr/bin/env bash
# Server Security Center — read-only VPS preflight check.
#
# This script only READS system state. It does not install packages, modify
# firewall rules, restart services, write files outside /tmp, or touch any
# secret. Safe to run on a live, unmodified VPS at any time.
#
# Usage: bash preflight.sh
set -uo pipefail

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  [OK]   %s\n' "$1"; }
warn() { printf '  [WARN] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; }
info() { printf '  [INFO] %s\n' "$1"; }

bold "== Operating System =="
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  info "$PRETTY_NAME"
  if [[ "${ID:-}" == "ubuntu" ]]; then
    major="${VERSION_ID%%.*}"
    if [[ "$major" -ge 20 ]]; then
      ok "Ubuntu $VERSION_ID is supported"
    else
      warn "Ubuntu $VERSION_ID is older than the tested baseline (20.04+)"
    fi
  else
    warn "Not Ubuntu (detected: ${ID:-unknown}) — this project targets Ubuntu, YMMV elsewhere"
  fi
else
  bad "Cannot read /etc/os-release"
fi

bold "== CPU =="
cpu_cores=$(nproc 2>/dev/null || echo "unknown")
info "Cores: $cpu_cores"
if [[ "$cpu_cores" =~ ^[0-9]+$ ]]; then
  if [[ "$cpu_cores" -ge 2 ]]; then
    ok "2+ cores available"
  else
    warn "Only 1 core detected — Postgres + API + worker will contend for CPU under load"
  fi
fi

bold "== Memory =="
if command -v free >/dev/null 2>&1; then
  total_mb=$(free -m | awk '/^Mem:/{print $2}')
  avail_mb=$(free -m | awk '/^Mem:/{print $7}')
  info "Total: ${total_mb} MB, Available: ${avail_mb} MB"
  if [[ "$total_mb" -ge 2048 ]]; then
    ok "2GB+ total RAM"
  elif [[ "$total_mb" -ge 1024 ]]; then
    warn "1-2GB RAM — workable but tight; see the lightweight-config notes below"
  else
    bad "Under 1GB RAM — not recommended for Postgres + API + worker + Caddy on one host"
  fi
else
  bad "free command not found"
fi

bold "== Disk =="
df -h / 2>/dev/null | awk 'NR==1{print "  "$0} NR==2{print "  "$0}'
avail_disk_gb=$(df --output=avail -BG / 2>/dev/null | tail -1 | tr -dc '0-9')
if [[ -n "${avail_disk_gb:-}" ]]; then
  if [[ "$avail_disk_gb" -ge 20 ]]; then
    ok "${avail_disk_gb}GB free on /"
  else
    warn "${avail_disk_gb}GB free on / — monitor growth of Postgres data and container images"
  fi
fi

bold "== System Load =="
if [[ -f /proc/loadavg ]]; then
  info "Load average (1/5/15m): $(cut -d' ' -f1-3 /proc/loadavg)"
fi

bold "== Docker =="
if command -v docker >/dev/null 2>&1; then
  docker_version=$(docker --version 2>/dev/null)
  ok "$docker_version"
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon is reachable by this user"
  else
    warn "Docker is installed but this user cannot reach the daemon (try with sudo, or add the user to the docker group)"
  fi
else
  bad "Docker is not installed — required before deployment"
fi

bold "== Docker Compose =="
if docker compose version >/dev/null 2>&1; then
  ok "$(docker compose version)"
elif command -v docker-compose >/dev/null 2>&1; then
  warn "Only the legacy standalone docker-compose was found ($(docker-compose --version)); the v2 'docker compose' plugin is preferred"
else
  bad "Docker Compose is not available — required before deployment"
fi

bold "== Listening Ports =="
if command -v ss >/dev/null 2>&1; then
  ss -tulnp 2>/dev/null | awk 'NR==1 || /LISTEN|UNCONN/' | head -30
else
  warn "ss not found — install iproute2 to inspect listening ports, or check manually"
fi

bold "== Port This Stack Actually Needs (18080, loopback only) =="
if command -v ss >/dev/null 2>&1 && ss -tuln 2>/dev/null | grep -q ":18080 "; then
  warn "Port 18080 is already in use — docker-compose.yml binds the API to 127.0.0.1:18080; change the mapping if this port is taken by something else"
else
  ok "Port 18080 is free"
fi

bold "== Ports This Stack Does NOT Use (informational — expected to already be taken) =="
for port in 80 443 8000; do
  if command -v ss >/dev/null 2>&1 && ss -tuln 2>/dev/null | grep -q ":${port} "; then
    info "Port ${port} is in use (expected — likely aaPanel's Nginx on 80/443, or an existing service on 8000). This stack never binds to it."
  else
    info "Port ${port} is free. This stack still won't bind to it — nothing to do here."
  fi
done
info "PostgreSQL (container-internal 5432) is never published to the host by this stack at all — no port check needed."

bold "== Existing Services on This Host (informational — this stack does not modify or replace any of these) =="
for svc in nginx apache2 mysql mysqld mariadb bt; do
  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$svc" 2>/dev/null; then
    info "$svc is running — left untouched by this stack."
  fi
done

bold "== Summary =="
echo "  Review any [WARN]/[FAIL] lines above before running 'docker compose up'."
echo "  This script changed nothing. Re-run any time."
