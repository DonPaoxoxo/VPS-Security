import logging

import httpx

from ssc_core.config import get_settings

logger = logging.getLogger("ssc.notify")


async def send_telegram_message(text: str) -> tuple[bool, str | None]:
    """Sends a message via the Telegram Bot API. Returns (success, error_detail).

    Credentials come from environment/settings only — never from the browser
    or any client-supplied value.
    """
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False, "Telegram credentials are not configured"

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            return False, f"Telegram API returned HTTP {resp.status_code}: {resp.text[:200]}"
        return True, None
    except httpx.HTTPError as exc:
        logger.warning("Telegram delivery failed: %s", exc)
        return False, str(exc)


def format_alert_message(
    *,
    alert_type: str,
    severity: str,
    server_name: str | None,
    domain: str | None,
    detail: str,
    timestamp: str,
    incident_url: str | None,
) -> str:
    lines = [f"<b>[{severity.upper()}] {alert_type}</b>"]
    if server_name:
        lines.append(f"Server: {server_name}")
    if domain:
        lines.append(f"Domain: {domain}")
    lines.append(f"Time (UTC): {timestamp}")
    lines.append(detail)
    if incident_url:
        lines.append(f'<a href="{incident_url}">View in dashboard</a>')
    return "\n".join(lines)
