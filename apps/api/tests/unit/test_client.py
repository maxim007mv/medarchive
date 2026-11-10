from ipaddress import IPv4Network, ip_address, ip_network
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.client import client_ip
from app.core.ratelimit import client_network

PROXY = "172.18.0.5"
TRUSTED = [ip_network("172.16.0.0/12")]


def _request(
    peer: str, forwarded: str | None = None, trusted: list[IPv4Network] | None = None
) -> Request:
    settings = SimpleNamespace(trusted_proxies=TRUSTED if trusted is None else trusted)
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    return Request(
        {
            "type": "http",
            "headers": headers,
            "client": (peer, 40000),
            "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
        }
    )


@pytest.mark.parametrize(
    ("forwarded", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("1.1.1.1, 203.0.113.7", "203.0.113.7"),
        ("203.0.113.7, 172.18.0.9", "203.0.113.7"),
        ("not-an-ip", PROXY),
        (None, PROXY),
    ],
    ids=["single-hop", "spoofed-left-hop", "chain-of-trusted-proxies", "garbage", "no-header"],
)
def test_client_behind_trusted_proxy(forwarded: str | None, expected: str) -> None:
    assert client_ip(_request(PROXY, forwarded)) == ip_address(expected)


def test_forwarded_header_from_untrusted_peer_is_ignored() -> None:
    assert client_ip(_request("198.51.100.4", "203.0.113.7")) == ip_address("198.51.100.4")


def test_without_trusted_proxies_the_peer_is_the_client() -> None:
    assert client_ip(_request(PROXY, "203.0.113.7", trusted=[])) == ip_address(PROXY)


def test_ipv6_clients_share_a_budget_per_64() -> None:
    first = _request("2001:db8:1:2::a", trusted=[])
    second = _request("2001:db8:1:2:ffff::b", trusted=[])

    assert client_network(first) == client_network(second) == "2001:db8:1:2::/64"
