from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.process_incoming_message import ProcessIncomingMessage
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, get_db
from app.domain.ports import (
    AIResponder,
    ConversationRepository,
    EscalationNotifier,
    IdempotencyStore,
    MessageGateway,
)
from app.infrastructure.ai.fake_ai_responder import FakeAIResponder
from app.infrastructure.ai.openai_conversation_responder import OpenAIConversationResponder
from app.infrastructure.cache.redis_idempotency_store import RedisIdempotencyStore
from app.infrastructure.messaging.meta_message_gateway import MetaMessageGateway
from app.infrastructure.notifications.fake_escalation_notifier import FakeEscalationNotifier
from app.infrastructure.notifications.telegram_escalation_notifier import (
    TelegramEscalationNotifier,
)
from app.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from app.infrastructure.persistence.sqlalchemy_conversation_repository import (
    SqlAlchemyConversationRepository,
)

# Singletons for mock/in-memory components to preserve state across requests in tests
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


async def get_conversation_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationRepository:
    if settings.app_env == "test":
        return _conversation_repository
    return SqlAlchemyConversationRepository(db)


async def get_ai_responder(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIResponder:
    if settings.app_env == "test" or not settings.openai_api_key.get_secret_value():
        return _ai_responder
    return OpenAIConversationResponder(
        api_key=settings.openai_api_key,
        model=settings.response_model,
        timeout_seconds=settings.openai_request_timeout_seconds,
        timezone_name=settings.app_timezone,
    )


async def get_escalation_notifier(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EscalationNotifier:
    if settings.app_env == "test" or not settings.telegram_bot_token.get_secret_value():
        return _escalation_notifier
    return TelegramEscalationNotifier(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        api_base_url=settings.telegram_api_base_url,
        timeout_seconds=settings.telegram_request_timeout_seconds,
        session_factory=SessionLocal,
    )


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
