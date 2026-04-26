import asyncio
import logging
from contextlib import suppress
from typing import Any, Dict, Optional

from .queue import RedisTaskQueue
from .repositories import get_network_setting, update_network_setting

logger = logging.getLogger(__name__)


class NetworkSettingsManager:
    def __init__(self, queue: RedisTaskQueue):
        self.queue = queue
        self._lock = asyncio.Lock()
        self._cache: Optional[Dict[str, Any]] = None
        self._version: int = 0
        self._listener_task: Optional[asyncio.Task] = None

    async def load_initial(self) -> Dict[str, Any]:
        async with self._lock:
            settings = get_network_setting()
            self._cache = settings
            self._version = int(settings.get("version") or 0)
            await self.queue.publish_network_version(self._version)
            return dict(settings)

    async def get_current(self) -> Dict[str, Any]:
        if self._cache is None:
            return await self.load_initial()
        return dict(self._cache)

    async def refresh(self) -> Dict[str, Any]:
        async with self._lock:
            settings = get_network_setting()
            self._cache = settings
            self._version = int(settings.get("version") or 0)
            return dict(settings)

    async def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            settings = update_network_setting(payload)
            self._cache = settings
            self._version = int(settings.get("version") or 0)
            await self.queue.publish_network_version(self._version)
            return dict(settings)

    async def start_listener(self) -> None:
        if self._listener_task and not self._listener_task.done():
            return
        self._listener_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self) -> None:
        while True:
            pubsub = None
            try:
                pubsub = await self.queue.get_network_pubsub()
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    try:
                        incoming_version = int(data)
                    except (TypeError, ValueError):
                        continue
                    if incoming_version > self._version:
                        await self.refresh()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("网络配置监听异常，将重试: %s", exc)
                await asyncio.sleep(1.0)
            finally:
                if pubsub is not None:
                    with suppress(Exception):
                        await pubsub.close()

    async def close(self) -> None:
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            with suppress(Exception):
                await self._listener_task

