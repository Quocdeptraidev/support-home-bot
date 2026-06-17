from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from app.application.use_cases.process_incoming_message import ProcessIncomingMessage
from app.core.config import Settings, get_settings
from app.domain.ports import (
    AIResponder,
    ConversationRepository,
    EscalationNotifier,
    IdempotencyStore,
    MessageGateway,
)
from app.infrastructure.ai.fake_ai_responder import FakeAIResponder
from app.infrastructure.cache.redis_idempotency_store import RedisIdempotencyStore
from app.infrastructure.messaging.meta_message_gateway import MetaMessageGateway
from app.infrastructure.notifications.fake_escalation_notifier import FakeEscalationNotifier
from app.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)

# Singletons for mock/in-memory components to preserve state across requests
_conversation_repository = InMemoryConversationRepository()
_ai_responder = FakeAIResponder()
_escalation_notifier = FakeEscalationNotifier()


async def get_redis(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[Redis]:
    client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def get_idempotency_store(
    redis: Annotated[Redis, Depends(get_redis)],
) -> IdempotencyStore:
    return RedisIdempotencyStore(redis)


async def get_conversation_repository() -> ConversationRepository:
    return _conversation_repository


async def get_ai_responder() -> AIResponder:
    return _ai_responder


async def get_escalation_notifier() -> EscalationNotifier:
    return _escalation_notifier


async def get_message_gateway(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageGateway:
    return MetaMessageGateway(
        page_access_token=settings.fb_page_access_token,
        api_version=settings.fb_api_version,
        graph_base_url=settings.fb_graph_base_url,
        timeout_seconds=settings.fb_request_timeout_seconds,
    )


async def get_process_incoming_message_use_case(
    ai_responder: Annotated[AIResponder, Depends(get_ai_responder)],
    conversation_repository: Annotated[
        ConversationRepository, Depends(get_conversation_repository)
    ],
    idempotency_store: Annotated[IdempotencyStore, Depends(get_idempotency_store)],
    message_gateway: Annotated[MessageGateway, Depends(get_message_gateway)],
    escalation_notifier: Annotated[EscalationNotifier, Depends(get_escalation_notifier)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProcessIncomingMessage:
    return ProcessIncomingMessage(
        ai_responder=ai_responder,
        conversation_repository=conversation_repository,
        idempotency_store=idempotency_store,
        message_gateway=message_gateway,
        escalation_notifier=escalation_notifier,
        history_limit=settings.ai_max_conversation_history,
        idempotency_ttl_seconds=settings.redis_idempotency_ttl_seconds,
        escalation_threshold=settings.ai_escalation_confidence_threshold,
    )
