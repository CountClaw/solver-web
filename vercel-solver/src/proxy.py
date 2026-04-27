from urllib.parse import urlparse

import requests
from requests import exceptions as req_exc

NETWORK_EXCEPTIONS = (
    req_exc.Timeout,
    req_exc.ConnectionError,
    req_exc.ProxyError,
    req_exc.SSLError,
)


def _normalize_no_proxy(no_proxy: str) -> list[str]:
    if not no_proxy:
        return []
    return [item.strip().lower() for item in no_proxy.split(",") if item.strip()]


def _host_matches_no_proxy(url: str, no_proxy: str) -> bool:
    hostname = (urlparse(url).hostname or "").strip().lower()
    if not hostname:
        return False

    for rule in _normalize_no_proxy(no_proxy):
        if hostname == rule:
            return True
        if rule.startswith(".") and hostname.endswith(rule):
            return True
        if hostname.endswith(f".{rule}"):
            return True
    return False


def _build_timeout(connect_timeout_ms: int, read_timeout_ms: int) -> tuple[float, float]:
    connect = max(0.2, connect_timeout_ms / 1000.0)
    read = max(0.2, read_timeout_ms / 1000.0)
    return connect, read


def request_with_proxy_fallback(
    session: requests.Session,
    method: str,
    url: str,
    *,
    proxy_url: str,
    no_proxy: str,
    connect_timeout_ms: int,
    read_timeout_ms: int,
    **kwargs,
) -> requests.Response:
    timeout = _build_timeout(connect_timeout_ms, read_timeout_ms)
    can_proxy = bool(proxy_url) and not _host_matches_no_proxy(url, no_proxy)

    if can_proxy:
        proxies = {"http": proxy_url, "https": proxy_url}
        try:
            return session.request(method, url, timeout=timeout, proxies=proxies, **kwargs)
        except NETWORK_EXCEPTIONS:
            return session.request(method, url, timeout=timeout, proxies=None, **kwargs)

    return session.request(method, url, timeout=timeout, proxies=None, **kwargs)


def is_network_exception(exc: Exception) -> bool:
    return isinstance(exc, NETWORK_EXCEPTIONS)
