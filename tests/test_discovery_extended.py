import os

from conftest import FIXTURES_DIR

import ssc_agent.discovery as discovery
from app.services.classification import classify


def test_laravel_app_detected_as_other_via_real_vhost(monkeypatch):
    sites_glob = os.path.join(FIXTURES_DIR, "vhost-aapanel-nginx", "*")
    monkeypatch.setattr(discovery, "NGINX_VHOST_GLOBS", [sites_glob])
    monkeypatch.setattr(discovery, "APACHE_VHOST_GLOBS", [])

    vhosts = discovery.discover_virtual_hosts()
    laravel = next(v for v in vhosts if "app.example.com" in v.hostnames)

    assert laravel.indicators["has_artisan_file"] is True
    assert laravel.indicators["has_composer_json"] is True
    assert laravel.indicators["has_wp_config"] is False

    result = classify(laravel.indicators)
    assert result.website_type.value == "other"


def test_reverse_proxied_nodejs_app_flagged_as_proxy(monkeypatch):
    sites_glob = os.path.join(FIXTURES_DIR, "vhost-aapanel-nginx", "*")
    monkeypatch.setattr(discovery, "NGINX_VHOST_GLOBS", [sites_glob])
    monkeypatch.setattr(discovery, "APACHE_VHOST_GLOBS", [])

    vhosts = discovery.discover_virtual_hosts()
    node_app = next(v for v in vhosts if "api.example.com" in v.hostnames)

    assert node_app.indicators["is_reverse_proxy"] is True


def test_two_vhost_files_sharing_a_document_root_merge_aliases(monkeypatch):
    # Simulates re-discovery / separate http+https server blocks for the same
    # site living in different config files — a common real-world aaPanel
    # layout. The agent-side merge must combine hostnames under one entry,
    # not report the same document root twice.
    sites_glob = os.path.join(FIXTURES_DIR, "multi-file-same-root", "*")
    monkeypatch.setattr(discovery, "NGINX_VHOST_GLOBS", [sites_glob])
    monkeypatch.setattr(discovery, "APACHE_VHOST_GLOBS", [])

    vhosts = discovery.discover_virtual_hosts()
    matching = [v for v in vhosts if "blog.example.com" in v.hostnames or "www.blog.example.com" in v.hostnames]

    assert len(matching) == 1, "expected both vhost files to merge into a single entry by document root"
    assert set(matching[0].hostnames) == {"blog.example.com", "www.blog.example.com"}
