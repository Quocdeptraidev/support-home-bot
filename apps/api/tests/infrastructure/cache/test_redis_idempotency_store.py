import uuid
from collections.abc import AsyncGenerator

import pytest
from redis.asyncio import Redis

from app.core.config import settings
from app.infrastructure.cache.redis_idempotency_store import RedisIdempotencyStore


@pytest.fixture
async def redis_client() -> AsyncGenerator[Redis]:
    client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()


async def test_redis_idempotency_store_lifecycle(redis_client: Redis) -> None:
    store = RedisIdempotencyStore(redis_client)
    event_id = f"test-event-{uuid.uuid4()}"
    key = f"idempotency:{event_id}"

    try:
        # First claim should succeed
        claimed = await store.claim(event_id, ttl_seconds=60)
        assert claimed is True

        # Second claim for the same event should fail
        claimed_again = await store.claim(event_id, ttl_seconds=60)
        assert claimed_again is False

        # Verify TTL is set
        ttl = await redis_client.ttl(key)
        assert 50 <= ttl <= 60

    finally:
        # Clean up the key
        await redis_client.delete(key)
