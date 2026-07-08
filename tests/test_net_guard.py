#!/usr/bin/env python3
"""P0-3: SSRF guard — block probes to internal/loopback/link-local addresses."""

from __future__ import annotations

from skillprism._net_guard import is_safe_url


def test_blocks_cloud_metadata_endpoint() -> None:
    assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False


def test_blocks_loopback() -> None:
    assert is_safe_url("http://127.0.0.1/") is False
    assert is_safe_url("http://localhost/") is False
    assert is_safe_url("http://[::1]/") is False


def test_blocks_private_ranges() -> None:
    assert is_safe_url("http://10.0.0.1/") is False
    assert is_safe_url("http://192.168.1.1/") is False
    assert is_safe_url("http://172.16.0.1/") is False


def test_blocks_unspecified_and_multicast() -> None:
    assert is_safe_url("http://0.0.0.0/") is False


def test_rejects_non_http() -> None:
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("ftp://example.com/") is False
    assert is_safe_url("") is False


def test_allows_public_literal_ip() -> None:
    # 8.8.8.8 is a public DNS IP.
    assert is_safe_url("http://8.8.8.8/") is True


def test_allows_public_hostname() -> None:
    # A well-known public hostname that resolves to a public address.
    assert is_safe_url("https://example.com/") is True


def test_unresolvable_hostname_is_unsafe() -> None:
    assert is_safe_url("http://this-host-does-not-exist-invalid.invalid/") is False
