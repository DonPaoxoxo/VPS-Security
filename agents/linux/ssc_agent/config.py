import json
import os
from dataclasses import dataclass

CREDENTIALS_PATH = "/etc/ssc-agent/credentials.json"
STATE_DIR = "/var/lib/ssc-agent"
WATCHED_PATHS_FILE = "/etc/ssc-agent/watched-paths.txt"

DEFAULT_WATCHED_PATHS = [
    "/etc/nginx",
    "/etc/apache2",
    "/etc/php",
]


@dataclass
class AgentCredentials:
    api_url: str
    server_id: str
    agent_id: str
    api_key: str


def load_credentials() -> AgentCredentials:
    if not os.path.exists(CREDENTIALS_PATH):
        raise SystemExit(
            f"No credentials found at {CREDENTIALS_PATH}. Run enroll.py first with an enrollment token."
        )
    with open(CREDENTIALS_PATH) as f:
        data = json.load(f)
    return AgentCredentials(
        api_url=data["api_url"], server_id=data["server_id"], agent_id=data["agent_id"], api_key=data["api_key"]
    )


def save_credentials(creds: AgentCredentials) -> None:
    os.makedirs(os.path.dirname(CREDENTIALS_PATH), exist_ok=True)
    with open(CREDENTIALS_PATH, "w") as f:
        json.dump(
            {
                "api_url": creds.api_url,
                "server_id": creds.server_id,
                "agent_id": creds.agent_id,
                "api_key": creds.api_key,
            },
            f,
            indent=2,
        )
    os.chmod(CREDENTIALS_PATH, 0o600)


def load_watched_paths() -> list[str]:
    if os.path.exists(WATCHED_PATHS_FILE):
        with open(WATCHED_PATHS_FILE) as f:
            paths = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        if paths:
            return paths
    return DEFAULT_WATCHED_PATHS
