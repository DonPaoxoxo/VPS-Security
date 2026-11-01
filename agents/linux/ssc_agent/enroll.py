"""One-time enrollment: exchanges a short-lived token (generated in the
dashboard's Add Server Wizard) for a permanent, independently revocable
agent API key, and writes it to /etc/ssc-agent/credentials.json.

Usage:
    python3 -m ssc_agent.enroll --api-url https://hub.example.com --token <token>
"""

import argparse
import platform
import sys

import requests

from ssc_agent.config import AgentCredentials, save_credentials

AGENT_VERSION = "0.1.0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Enroll this server's monitoring agent")
    parser.add_argument("--api-url", required=True, help="Base URL of the central monitoring API")
    parser.add_argument("--token", required=True, help="One-time enrollment token from the dashboard")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    resp = requests.post(
        f"{api_url}/agents/enroll",
        json={"enrollment_token": args.token, "agent_version": AGENT_VERSION},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"Enrollment failed: HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    creds = AgentCredentials(
        api_url=api_url, server_id=data["server_id"], agent_id=data["agent_id"], api_key=data["api_key"]
    )
    save_credentials(creds)
    print(f"Enrolled successfully as agent {creds.agent_id} for server {creds.server_id}.")
    print(f"Detected OS: {platform.platform()}")
    print("Credentials saved to /etc/ssc-agent/credentials.json (mode 0600).")


if __name__ == "__main__":
    main()
