#!/usr/bin/env bash
# Server Security Center — agent installer.
#
# Usage:
#   curl -fsSL https://your-hub.example.com/static/install-agent.sh | sudo bash -s -- \
#       --api-url https://your-hub.example.com --token <one-time-enrollment-token>
#
# This script only installs the agent and enrolls it with the credentials
# the dashboard issued for THIS server. It does not open any inbound ports,
# does not touch firewall rules, and does not modify any other software on
# this host.
set -euo pipefail

API_URL=""
TOKEN=""
INSTALL_DIR="/opt/ssc-agent"
AGENT_SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url) API_URL="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$API_URL" || -z "$TOKEN" ]]; then
  echo "Usage: install.sh --api-url <url> --token <enrollment-token>" >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "This installer must be run as root (it installs a systemd service)." >&2
  exit 1
fi

echo "==> Installing to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$AGENT_SOURCE_DIR"/ssc_agent "$INSTALL_DIR"/
cp "$AGENT_SOURCE_DIR"/requirements.txt "$INSTALL_DIR"/

echo "==> Creating virtualenv"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

echo "==> Enrolling with the monitoring hub"
mkdir -p /etc/ssc-agent /var/lib/ssc-agent
(cd "$INSTALL_DIR" && PYTHONPATH="$INSTALL_DIR" "$INSTALL_DIR/venv/bin/python" -m ssc_agent.enroll --api-url "$API_URL" --token "$TOKEN")

echo "==> Installing systemd service"
cp "$AGENT_SOURCE_DIR"/ssc-agent.service /etc/systemd/system/ssc-agent.service
systemctl daemon-reload
systemctl enable ssc-agent
systemctl restart ssc-agent

echo "==> Done. Check status with: systemctl status ssc-agent"
echo "==> Logs: journalctl -u ssc-agent -f"
