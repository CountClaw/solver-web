import requests

from src.proxy import _host_matches_no_proxy, request_with_proxy_fallback


class DummyResponse:
    pass


class FakeSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, timeout=None, proxies=None, **kwargs):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "timeout": timeout,
                "proxies": proxies,
            }
        )
        if len(self.calls) == 1 and proxies:
            raise requests.exceptions.ProxyError("proxy unavailable")
        return DummyResponse()


def test_no_proxy_exact_match():
    assert _host_matches_no_proxy("http://localhost:5072/result", "localhost,127.0.0.1")


def test_no_proxy_suffix_match():
    assert _host_matches_no_proxy("https://a.b.example.com/api", ".example.com")


def test_no_proxy_not_match():
    assert not _host_matches_no_proxy("https://api.example.net/ping", "example.com")


def test_proxy_fallback_to_direct():
    session = FakeSession()
    result = request_with_proxy_fallback(
        session,
        "GET",
        "https://solver.example.com/result?id=1",
        proxy_url="http://127.0.0.1:7897",
        no_proxy="localhost,127.0.0.1,::1",
        connect_timeout_ms=2500,
        read_timeout_ms=5000,
    )

    assert isinstance(result, DummyResponse)
    assert session.calls[0]["proxies"] == {
        "http": "http://127.0.0.1:7897",
        "https": "http://127.0.0.1:7897",
    }
    assert session.calls[1]["proxies"] is None


def test_no_proxy_skips_proxy_request():
    session = FakeSession()
    result = request_with_proxy_fallback(
        session,
        "GET",
        "http://localhost:5072/result?id=1",
        proxy_url="http://127.0.0.1:7897",
        no_proxy="localhost,127.0.0.1,::1",
        connect_timeout_ms=2500,
        read_timeout_ms=5000,
    )

    assert isinstance(result, DummyResponse)
    assert len(session.calls) == 1
    assert session.calls[0]["proxies"] is None
