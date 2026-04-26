from typing import Any, Dict, Optional
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
    rules = _normalize_no_proxy(no_proxy)
    for rule in rules:
        if hostname == rule:
            return True
        if rule.startswith(".") and hostname.endswith(rule):
            return True
        if hostname.endswith(f".{rule}"):
            return True
    return False


def _build_timeout(network_setting: Dict[str, Any], default_connect: int, default_read: int) -> tuple[float, float]:
    connect_ms = int(network_setting.get("connectTimeoutMs") or default_connect)
    read_ms = int(network_setting.get("readTimeoutMs") or default_read)
    connect = max(0.2, connect_ms / 1000.0)
    read = max(0.2, read_ms / 1000.0)
    return connect, read


def request_with_proxy_fallback(
    session: requests.Session,
    method: str,
    url: str,
    network_setting: Dict[str, Any],
    *,
    default_connect_timeout_ms: int,
    default_read_timeout_ms: int,
    **kwargs,
) -> requests.Response:
    no_proxy = str(network_setting.get("noProxy") or "localhost,127.0.0.1,::1")
    timeout = _build_timeout(network_setting, default_connect_timeout_ms, default_read_timeout_ms)
    enabled = bool(network_setting.get("enabled"))
    proxy_url = str(network_setting.get("proxyURL") or "").strip()
    bypass_proxy = _host_matches_no_proxy(url, no_proxy)
    can_proxy = enabled and bool(proxy_url) and not bypass_proxy

    if can_proxy:
        proxies = {"http": proxy_url, "https": proxy_url}
        try:
            return session.request(method, url, timeout=timeout, proxies=proxies, **kwargs)
        except NETWORK_EXCEPTIONS:
            # 代理不可用时回退直连
            return session.request(method, url, timeout=timeout, proxies=None, **kwargs)

    return session.request(method, url, timeout=timeout, proxies=None, **kwargs)


def is_network_exception(exc: Exception) -> bool:
    return isinstance(exc, NETWORK_EXCEPTIONS)

