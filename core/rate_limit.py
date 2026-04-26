import time
from typing import Tuple

import redis.asyncio as redis


async def check_api_rate_limit(
    redis_client: redis.Redis,
    api_key: str,
    per_second: int,
    per_minute: int,
) -> Tuple[bool, int]:
    """
    返回值:
    - (True, 0): 允许请求
    - (False, retry_after_seconds): 已限流
    """
    now = int(time.time())
    sec_key = f"rl:s:{api_key}:{now}"
    min_key = f"rl:m:{api_key}:{now // 60}"

    sec_count = await redis_client.incr(sec_key)
    if sec_count == 1:
        await redis_client.expire(sec_key, 2)
    if sec_count > max(1, int(per_second)):
        return False, 1

    min_count = await redis_client.incr(min_key)
    if min_count == 1:
        await redis_client.expire(min_key, 70)
    if min_count > max(1, int(per_minute)):
        return False, 60 - (now % 60)

    return True, 0

