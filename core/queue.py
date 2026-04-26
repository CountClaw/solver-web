from typing import Dict, List, Tuple

import redis.asyncio as redis
from redis.exceptions import ResponseError

from .config import AppConfig, load_config


class RedisTaskQueue:
    def __init__(self, cfg: AppConfig | None = None):
        self.cfg = cfg or load_config()
        self.client = redis.from_url(self.cfg.redis_url, decode_responses=True)

    async def ensure_group(self) -> None:
        try:
            await self.client.xgroup_create(
                name=self.cfg.task_stream,
                groupname=self.cfg.task_group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue_task(self, task_payload: Dict[str, str]) -> str:
        payload = {key: str(value) for key, value in task_payload.items() if value is not None}
        return await self.client.xadd(
            self.cfg.task_stream,
            payload,
            maxlen=self.cfg.task_stream_maxlen,
            approximate=True,
        )

    async def read_tasks(self, consumer_name: str, count: int | None = None, block_ms: int | None = None) -> List[Tuple[str, List[Tuple[str, Dict[str, str]]]]]:
        safe_count = count or self.cfg.task_read_count
        safe_block = block_ms or self.cfg.task_block_ms
        return await self.client.xreadgroup(
            groupname=self.cfg.task_group,
            consumername=consumer_name,
            streams={self.cfg.task_stream: ">"},
            count=safe_count,
            block=safe_block,
        )

    async def ack_task(self, message_id: str) -> int:
        return await self.client.xack(self.cfg.task_stream, self.cfg.task_group, message_id)

    async def publish_network_version(self, version: int) -> None:
        await self.client.set(self.cfg.network_settings_version_key, int(version))
        await self.client.publish(self.cfg.network_settings_channel, int(version))

    async def get_network_version(self) -> int:
        raw = await self.client.get(self.cfg.network_settings_version_key)
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    async def get_network_pubsub(self):
        pubsub = self.client.pubsub()
        await pubsub.subscribe(self.cfg.network_settings_channel)
        return pubsub

    async def close(self) -> None:
        await self.client.close()

