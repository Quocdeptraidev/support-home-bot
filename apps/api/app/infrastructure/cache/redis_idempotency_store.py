from redis.asyncio import Redis

from app.domain.ports import IdempotencyStore


class RedisIdempotencyStore(IdempotencyStore):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def claim(self, event_id: str, ttl_seconds: int) -> bool:
        key = f"idempotency:{event_id}"
        result = await self._redis.set(key, "1", ex=ttl_seconds, nx=True)
        return bool(result)
