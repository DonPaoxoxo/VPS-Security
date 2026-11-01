"""SSRF guard for outbound monitoring checks.

Domains monitored by this platform are only ever added after an owner
explicitly approves them in the Domain Inventory review step — but a vhost's
server_name is still attacker-influenceable data (anyone who can get a config
onto a monitored server could point a hostname at an internal address to turn
the monitoring worker into an SSRF probe). Resolve and validate before every
outbound request rather than trusting a domain string at face value.
"""

import ipaddress
import socket

_DISALLOWED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # shared address space (CGNAT)
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local, incl. cloud metadata endpoints
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),  # multicast
    ipaddress.ip_network("240.0.0.0/4"),  # reserved
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # unique local
    ipaddress.ip_network("fe80::/10"),  # link-local
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped — checked after unwrapping too
]


def _is_disallowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    return any(ip in net for net in _DISALLOWED_NETWORKS)


def resolve_all_addresses(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return []
    return sorted({info[4][0] for info in infos})


def is_safe_monitoring_target(hostname: str) -> tuple[bool, str]:
    """Resolves `hostname` and returns (is_safe, reason). A hostname that
    resolves to ANY private/loopback/link-local/reserved address is rejected
    outright, even if it also resolves to a public one — a classic DNS
    rebinding setup presents both."""
    addresses = resolve_all_addresses(hostname)
    if not addresses:
        return False, f"DNS resolution failed for {hostname}"

    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False, f"Could not parse resolved address {addr!r}"
        if _is_disallowed(ip):
            return False, f"{hostname} resolves to non-public address {addr} — refusing to probe it"

    return True, "ok"
