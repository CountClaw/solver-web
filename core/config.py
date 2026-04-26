import os
import socket
from dataclasses import dataclass
from functools import lru_cache
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _to_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _to_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _to_list(name: str, default: str) -> List[str]:
    raw = (os.getenv(name) or default).strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class AppConfig:
    database_url: str
    redis_url: str
    task_stream: str
    task_group: str
    task_consumer_name: str
    task_read_count: int
    task_block_ms: int
    task_stream_maxlen: int
    worker_max_attempts: int
    worker_retry_delay_ms: int
    solver_node_urls: List[str]
    solver_poll_interval_ms: int
    solver_max_wait_seconds: int
    solver_connect_timeout_ms: int
    solver_read_timeout_ms: int
    admin_token: str
    network_settings_channel: str
    network_settings_version_key: str
    default_no_proxy: str
    api_default_rate_second: int
    api_default_rate_minute: int
    api_host: str
    api_port: int
    admin_host: str
    admin_port: int


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    consumer = os.getenv("TASK_CONSUMER_NAME", "").strip()
    if not consumer:
        consumer = f"{socket.gethostname()}-{os.getpid()}"

    solver_urls = _to_list("SOLVER_NODE_URLS", "http://127.0.0.1:5072")

    return AppConfig(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/solver-web.db").strip(),
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip(),
        task_stream=os.getenv("TASK_STREAM", "solver_tasks").strip(),
        task_group=os.getenv("TASK_GROUP", "solver_workers").strip(),
        task_consumer_name=consumer,
        task_read_count=_to_int("TASK_READ_COUNT", 10, 1),
        task_block_ms=_to_int("TASK_BLOCK_MS", 5000, 100),
        task_stream_maxlen=_to_int("TASK_STREAM_MAXLEN", 20000, 1000),
        worker_max_attempts=_to_int("WORKER_MAX_ATTEMPTS", 3, 1),
        worker_retry_delay_ms=_to_int("WORKER_RETRY_DELAY_MS", 1000, 0),
        solver_node_urls=solver_urls,
        solver_poll_interval_ms=_to_int("SOLVER_POLL_INTERVAL_MS", 250, 50),
        solver_max_wait_seconds=_to_int("SOLVER_MAX_WAIT_SECONDS", 40, 5),
        solver_connect_timeout_ms=_to_int("SOLVER_CONNECT_TIMEOUT_MS", 2500, 500),
        solver_read_timeout_ms=_to_int("SOLVER_READ_TIMEOUT_MS", 5000, 500),
        admin_token=os.getenv("ADMIN_TOKEN", "change-me-admin-token").strip(),
        network_settings_channel=os.getenv("NETWORK_SETTINGS_CHANNEL", "network_settings_update").strip(),
        network_settings_version_key=os.getenv("NETWORK_SETTINGS_VERSION_KEY", "network_settings_version").strip(),
        default_no_proxy=os.getenv("DEFAULT_NO_PROXY", "localhost,127.0.0.1,::1").strip(),
        api_default_rate_second=_to_int("API_DEFAULT_RATE_SECOND", 5, 1),
        api_default_rate_minute=_to_int("API_DEFAULT_RATE_MINUTE", 120, 1),
        api_host=os.getenv("API_HOST", "0.0.0.0").strip(),
        api_port=_to_int("API_PORT", 8080, 1),
        admin_host=os.getenv("ADMIN_HOST", "0.0.0.0").strip(),
        admin_port=_to_int("ADMIN_PORT", 8090, 1),
    )

