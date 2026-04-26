from core.proxy import _host_matches_no_proxy


def test_no_proxy_exact_match():
    assert _host_matches_no_proxy("http://localhost:5072/result", "localhost,127.0.0.1")


def test_no_proxy_suffix_match():
    assert _host_matches_no_proxy("https://a.b.example.com/api", ".example.com")


def test_no_proxy_not_match():
    assert not _host_matches_no_proxy("https://api.example.net/ping", "example.com")

