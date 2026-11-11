from ipaddress import IPv4Address, IPv6Address, ip_address

from fastapi import Request
from pydantic import IPvAnyNetwork

IpAddress = IPv4Address | IPv6Address


def client_ip(request: Request) -> IpAddress | None:
    """Address of the person behind the request.

    The browser reaches the API only through the Next.js proxy (ADR-048), so the TCP peer is
    the proxy. Behind a trusted proxy the client is the nearest X-Forwarded-For hop that is not
    itself trusted; everything left of it could be typed by the client and is ignored.
    """
    peer = _parse(request.client.host if request.client else None)
    trusted: list[IPvAnyNetwork] = request.app.state.settings.trusted_proxies
    if peer is None or not _is_trusted(peer, trusted):
        return peer
    hops = [
        hop.strip()
        for header in request.headers.getlist("x-forwarded-for")
        for hop in header.split(",")
    ]
    for hop in reversed(hops):
        address = _parse(hop)
        if address is None:
            return peer
        if not _is_trusted(address, trusted):
            return address
    return peer


def _parse(host: str | None) -> IpAddress | None:
    try:
        return ip_address(host) if host else None
    except ValueError:
        return None


def _is_trusted(address: IpAddress, trusted: list[IPvAnyNetwork]) -> bool:
    return any(address in network for network in trusted)
