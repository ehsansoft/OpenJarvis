"""Transport policy for configurable local sibling services."""

import ipaddress
from urllib.parse import urlsplit


def trust_environment_for_url(url: str) -> bool:
    """Keep remote proxy settings, but never proxy loopback model/audio data."""
    try:
        host = urlsplit(url).hostname or ""
        if host.rstrip(".").lower() == "localhost":
            return False
        address = ipaddress.ip_address(host)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return not address.is_loopback
    except ValueError:
        return True
