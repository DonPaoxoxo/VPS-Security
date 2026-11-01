"""Read-only website discovery: parses installed Nginx/Apache virtual host
configuration files (including those managed by aaPanel, which simply writes
standard Nginx/Apache vhost files under the same directories) and inspects
each document root for structural indicators only — never database
credentials or file contents beyond existence/name checks.
"""

import glob
import os
import re
from dataclasses import dataclass, field

NGINX_VHOST_GLOBS = [
    "/etc/nginx/sites-enabled/*",
    "/etc/nginx/conf.d/*.conf",
    "/www/server/panel/vhost/nginx/*.conf",  # aaPanel-managed Nginx vhosts
]
APACHE_VHOST_GLOBS = [
    "/etc/apache2/sites-enabled/*.conf",
    "/www/server/panel/vhost/apache/*.conf",  # aaPanel-managed Apache vhosts
]

_SERVER_NAME_RE = re.compile(r"server_name\s+([^;]+);")
_ROOT_RE = re.compile(r"\broot\s+([^;]+);")
_LISTEN_SSL_RE = re.compile(r"listen\s+\d+\s+ssl")
_LISTEN_PORT_RE = re.compile(r"listen\s+(\d+)")
_PROXY_PASS_RE = re.compile(r"proxy_pass\s+[^;]+;")
_RETURN_REDIRECT_RE = re.compile(r"return\s+30[12378]\s+([^;]+);")

_APACHE_SERVERNAME_RE = re.compile(r"ServerName\s+(\S+)", re.IGNORECASE)
_APACHE_SERVERALIAS_RE = re.compile(r"ServerAlias\s+([^\n]+)", re.IGNORECASE)
_APACHE_DOCROOT_RE = re.compile(r"DocumentRoot\s+(\S+)", re.IGNORECASE)
_APACHE_PROXYPASS_RE = re.compile(r"ProxyPass\s+", re.IGNORECASE)


@dataclass
class DiscoveredVHost:
    document_root: str
    web_server: str
    hostnames: list[str]
    configured_port: int | None = None
    ssl_available: bool = False
    redirect_target: str | None = None
    indicators: dict[str, bool] = field(default_factory=dict)


def discover_virtual_hosts() -> list[DiscoveredVHost]:
    vhosts: list[DiscoveredVHost] = []
    vhosts.extend(_discover_nginx())
    vhosts.extend(_discover_apache())
    return _dedupe_by_document_root(vhosts)


def _discover_nginx() -> list[DiscoveredVHost]:
    results = []
    for pattern in NGINX_VHOST_GLOBS:
        for path in glob.glob(pattern):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue

            server_blocks = re.split(r"\bserver\s*\{", content)[1:]
            for block in server_blocks:
                hostnames_match = _SERVER_NAME_RE.search(block)
                if not hostnames_match:
                    continue
                hostnames = [h for h in hostnames_match.group(1).split() if h not in ("_", "")]
                if not hostnames:
                    continue

                root_match = _ROOT_RE.search(block)
                document_root = root_match.group(1).strip() if root_match else ""
                if not document_root:
                    continue

                ssl = bool(_LISTEN_SSL_RE.search(block))
                port_match = _LISTEN_PORT_RE.search(block)
                port = int(port_match.group(1)) if port_match else (443 if ssl else 80)
                redirect_match = _RETURN_REDIRECT_RE.search(block)
                redirect_target = redirect_match.group(1).strip().strip('"') if redirect_match else None
                is_proxy = bool(_PROXY_PASS_RE.search(block))

                indicators = _inspect_document_root(document_root)
                indicators["is_reverse_proxy"] = is_proxy

                results.append(
                    DiscoveredVHost(
                        document_root=document_root,
                        web_server="nginx",
                        hostnames=hostnames,
                        configured_port=port,
                        ssl_available=ssl,
                        redirect_target=redirect_target,
                        indicators=indicators,
                    )
                )
    return results


def _discover_apache() -> list[DiscoveredVHost]:
    results = []
    for pattern in APACHE_VHOST_GLOBS:
        for path in glob.glob(pattern):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue

            vhost_blocks = re.findall(r"<VirtualHost[^>]*>(.*?)</VirtualHost>", content, re.DOTALL | re.IGNORECASE)
            ssl = "443" in path or re.search(r"<VirtualHost[^>]*:443", content) is not None

            for block in vhost_blocks:
                name_match = _APACHE_SERVERNAME_RE.search(block)
                if not name_match:
                    continue
                hostnames = [name_match.group(1)]
                alias_match = _APACHE_SERVERALIAS_RE.search(block)
                if alias_match:
                    hostnames.extend(alias_match.group(1).split())

                docroot_match = _APACHE_DOCROOT_RE.search(block)
                document_root = docroot_match.group(1).strip('"') if docroot_match else ""
                if not document_root:
                    continue

                is_proxy = bool(_APACHE_PROXYPASS_RE.search(block))
                indicators = _inspect_document_root(document_root)
                indicators["is_reverse_proxy"] = is_proxy

                results.append(
                    DiscoveredVHost(
                        document_root=document_root,
                        web_server="apache",
                        hostnames=hostnames,
                        configured_port=443 if ssl else 80,
                        ssl_available=ssl,
                        indicators=indicators,
                    )
                )
    return results


def _inspect_document_root(document_root: str) -> dict[str, bool]:
    """Structural, read-only indicators only: file/directory existence. Never
    opens wp-config.php or any file that could contain credentials."""
    exists = os.path.isdir(document_root)

    def has(*rel_paths: str) -> bool:
        return exists and any(
            os.path.exists(os.path.join(document_root, rel)) for rel in rel_paths
        )

    indicators = {
        "has_wp_config": has("wp-config.php", "../wp-config.php"),
        "has_wp_content_dir": has("wp-content"),
        "has_wp_includes_dir": has("wp-includes"),
        "has_wp_admin_dir": has("wp-admin"),
        "has_artisan_file": has("artisan"),
        "has_composer_json": has("composer.json"),
        "has_package_json_server": has("package.json") and not has("index.html") and _looks_like_node_server(document_root),
        "has_server_side_php_files": exists and _has_php_files(document_root),
        "has_spa_build_markers": has("dist", "build") and has("index.html"),
    }

    if exists:
        entries = set(os.listdir(document_root)) if os.path.isdir(document_root) else set()
        non_asset_entries = entries - {"css", "js", "img", "images", "assets", "fonts", ".well-known"}
        only_static = "index.html" in entries and not any(
            e.endswith((".php", ".py", ".rb")) for e in non_asset_entries
        )
        indicators["is_static_site_config"] = only_static and not indicators["has_wp_config"]
        indicators["has_index_html_only"] = entries.issubset(
            {"index.html", "css", "js", "img", "images", "assets", "fonts", "favicon.ico", ".well-known"}
        )
    else:
        indicators["is_static_site_config"] = False
        indicators["has_index_html_only"] = False

    return indicators


def _has_php_files(document_root: str, max_check: int = 50) -> bool:
    checked = 0
    for _root, _dirs, files in os.walk(document_root):
        for name in files:
            if name.endswith(".php"):
                return True
            checked += 1
            if checked >= max_check:
                return False
    return False


def _looks_like_node_server(document_root: str) -> bool:
    package_json = os.path.join(document_root, "package.json")
    if not os.path.isfile(package_json):
        return False
    try:
        with open(package_json, errors="ignore") as f:
            content = f.read()
    except OSError:
        return False
    return '"start"' in content or '"express"' in content or '"fastify"' in content


def _dedupe_by_document_root(vhosts: list[DiscoveredVHost]) -> list[DiscoveredVHost]:
    merged: dict[str, DiscoveredVHost] = {}
    for vhost in vhosts:
        key = vhost.document_root
        if key not in merged:
            merged[key] = vhost
        else:
            existing_hosts = set(merged[key].hostnames)
            for h in vhost.hostnames:
                if h not in existing_hosts:
                    merged[key].hostnames.append(h)
                    existing_hosts.add(h)
    return list(merged.values())
