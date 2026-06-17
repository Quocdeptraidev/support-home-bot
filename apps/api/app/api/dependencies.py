from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from app.core.config import settings
from app.domain.ports import IdempotencyStore
from app.infrastructure.cache.redis_idempotency_store import RedisIdempotencyStore


async def get_redis() -> AsyncGenerator[Redis]:
    client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def get_idempotency_store(
    redis: Annotated[Redis, Depends(get_redis)],
) -> IdempotencyStore:
    return RedisIdempotencyStore(redis)
