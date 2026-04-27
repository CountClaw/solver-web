import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _to_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _to_list(name: str, default: str = "") -> tuple[str, ...]:
    raw = (os.getenv(name) or default).strip()
    if not raw:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    client_keys: tuple[str, ...]
    solver_node_urls: tuple[str, ...]
    solver_poll_interval_ms: int
    solver_max_wait_seconds: int
    solver_connect_timeout_ms: int
    solver_read_timeout_ms: int
    outbound_proxy_url: str
    outbound_no_proxy: str


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings(
        client_keys=_to_list("CLIENT_KEYS"),
        solver_node_urls=_to_list("SOLVER_NODE_URLS", "http://127.0.0.1:5072"),
        solver_poll_interval_ms=_to_int("SOLVER_POLL_INTERVAL_MS", 250, 50),
        solver_max_wait_seconds=_to_int("SOLVER_MAX_WAIT_SECONDS", 40, 5),
        solver_connect_timeout_ms=_to_int("SOLVER_CONNECT_TIMEOUT_MS", 2500, 200),
        solver_read_timeout_ms=_to_int("SOLVER_READ_TIMEOUT_MS", 5000, 200),
        outbound_proxy_url=(
            os.getenv("OUTBOUND_PROXY_URL")
            or os.getenv("HTTPS_PROXY")
            or os.getenv("HTTP_PROXY")
            or ""
        ).strip(),
        outbound_no_proxy=(os.getenv("OUTBOUND_NO_PROXY") or os.getenv("NO_PROXY") or "localhost,127.0.0.1,::1").strip(),
    )
