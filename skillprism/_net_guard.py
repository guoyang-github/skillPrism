#!/usr/bin/env python3
"""SSRF guard: block probes to internal / link-local / loopback addresses.

``smoke_test_runner._probe_api_endpoint`` previously issued ``curl -I`` against
any URL extracted from SKILL.md, including cloud-metadata endpoints
(``169.254.169.254``) and internal services. ``is_safe_url`` returns False for
URLs resolving to private/loopback/link-local/metadata addresses so the probe
skips them.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from typing import cast


def _is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unresolved / invalid → treat as unsafe
    # Loopback, private, link-local (incl. 169.254/16 cloud metadata),
    # unspecified, reserved, multicast.
    return bool(
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_unspecified
        or addr.is_reserved
        or addr.is_multicast
    )


def is_safe_url(url: str) -> bool:
    """Return True if ``url`` targets a public, non-internal host."""
    if not url:
        return False
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    # Literal IP in the URL.
    try:
        ipaddress.ip_address(host)
        return not _is_blocked_ip(host)
    except ValueError:
        pass
    # Hostname: resolve and reject if any address is internal.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False  # unresolvable → unsafe to probe
    for family, _, _, _, sockaddr in infos:
        ip = cast(str, sockaddr[0])
        # Strip IPv6 scope id / zone.
        if "%" in ip:
            ip = ip.split("%", 1)[0]
        if _is_blocked_ip(ip):
            return False
    return True
