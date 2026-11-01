import os

from conftest import FIXTURES_DIR

import ssc_agent.discovery as discovery


def _patch_globs(monkeypatch):
    sites_glob = os.path.join(FIXTURES_DIR, "sites-enabled", "*")
    monkeypatch.setattr(discovery, "NGINX_VHOST_GLOBS", [sites_glob])
    monkeypatch.setattr(discovery, "APACHE_VHOST_GLOBS", [])


def test_discovers_wordpress_and_static_vhosts(monkeypatch):
    _patch_globs(monkeypatch)
    vhosts = discovery.discover_virtual_hosts()
    by_host = {h: v for v in vhosts for h in v.hostnames}

    assert "example.com" in by_host
    wp = by_host["example.com"]
    assert wp.ssl_available is True
    assert wp.indicators["has_wp_config"] is True

    assert "static.example.com" in by_host
    static = by_host["static.example.com"]
    assert static.indicators["is_static_site_config"] is True
    assert static.indicators["has_wp_config"] is False


def test_www_alias_merges_into_primary_hostname_list(monkeypatch):
    _patch_globs(monkeypatch)
    vhosts = discovery.discover_virtual_hosts()
    wp = next(v for v in vhosts if "example.com" in v.hostnames)
    assert "www.example.com" in wp.hostnames
