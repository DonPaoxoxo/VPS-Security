from ssc_core.net_safety import is_safe_monitoring_target


def test_public_domain_is_safe():
    is_safe, _ = is_safe_monitoring_target("example.com")
    assert is_safe is True


def test_loopback_hostname_is_rejected():
    is_safe, reason = is_safe_monitoring_target("localhost")
    assert is_safe is False
    assert "127.0.0.1" in reason


def test_raw_private_ip_is_rejected():
    is_safe, _ = is_safe_monitoring_target("10.0.0.5")
    assert is_safe is False


def test_cloud_metadata_address_is_rejected():
    is_safe, _ = is_safe_monitoring_target("169.254.169.254")
    assert is_safe is False


def test_unresolvable_hostname_is_rejected():
    is_safe, reason = is_safe_monitoring_target("this-domain-should-not-resolve.invalid")
    assert is_safe is False
    assert "DNS resolution failed" in reason
