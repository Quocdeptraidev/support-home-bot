from collections.abc import AsyncGenerator
from functools import lru_cache
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.process_incoming_message import ProcessIncomingMessage
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, get_db
from app.domain.ports import (
    AIResponder,
    BookingRepository,
    CalendarGateway,
    ConversationRepository,
    EscalationNotifier,
    IdempotencyStore,
    MessageGateway,
    RoomRepository,
)
from app.infrastructure.ai.fake_ai_responder import FakeAIResponder
from app.infrastructure.ai.openai_conversation_responder import OpenAIConversationResponder
from app.infrastructure.cache.redis_idempotency_store import RedisIdempotencyStore
from app.infrastructure.messaging.meta_message_gateway import MetaMessageGateway
from app.infrastructure.notifications.fake_escalation_notifier import FakeEscalationNotifier
from app.infrastructure.notifications.telegram_escalation_notifier import (
    TelegramEscalationNotifier,
)
from app.infrastructure.persistence.in_memory_booking_repository import InMemoryBookingRepository
from app.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from app.infrastructure.persistence.in_memory_room_repository import InMemoryRoomRepository
from app.infrastructure.persistence.sqlalchemy_booking_repository import (
    SqlAlchemyBookingRepository,
)
from app.infrastructure.persistence.sqlalchemy_conversation_repository import (
    SqlAlchemyConversationRepository,
)
from app.infrastructure.persistence.sqlalchemy_room_repository import SqlAlchemyRoomRepository

from app.infrastructure.calendar.fake_calendar_adapter import FakeCalendarAdapter
from app.infrastructure.calendar.google_calendar_adapter import GoogleCalendarAdapter

# Singletons for mock/in-memory components to preserve state across requests in tests
_conversation_repository = InMemoryConversationRepository()
_ai_responder = FakeAIResponder()
_escalation_notifier = FakeEscalationNotifier()
_room_repository = InMemoryRoomRepository()
_booking_repository = InMemoryBookingRepository()
_calendar_gateway = FakeCalendarAdapter()


@lru_cache
def load_prompts() -> dict:
    current_dir = Path(__file__).resolve().parent
    prompts_dir = current_dir.parent / "core" / "prompts"

    prompts = {
        "system": {},
        "fewshot": {}
    }

    # Nạp các file system prompts
    system_dir = prompts_dir / "system"
    for name in ["receptionist", "booking", "faq"]:
        file_path = system_dir / f"{name}.json"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                prompts["system"][name] = json.load(f)
        except Exception:
            prompts["system"][name] = {}

    # Nạp fewshot examples
    fewshot_path = prompts_dir / "fewshot" / "booking_examples.json"
    try:
        with open(fewshot_path, "r", encoding="utf-8") as f:
            prompts["fewshot"]["booking_examples"] = json.load(f)
    except Exception:
        prompts["fewshot"]["booking_examples"] = []

    return prompts


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


async def get_room_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RoomRepository:
    if settings.app_env == "test":
        return _room_repository
    return SqlAlchemyRoomRepository(db)


async def get_booking_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingRepository:
    if settings.app_env == "test":
        return _booking_repository
    return SqlAlchemyBookingRepository(db)


async def get_ai_responder(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIResponder:
    if settings.app_env == "test" or not settings.openai_api_key.get_secret_value():
        return _ai_responder
    prompts = load_prompts()

    receptionist = prompts["system"].get("receptionist", {})
    booking = prompts["system"].get("booking", {})
    faq = prompts["system"].get("faq", {})
    fewshot = prompts["fewshot"].get("booking_examples", [])

    # Xây dựng System Prompt hoàn chỉnh bằng cách ghép các file JSON
    system_parts = []

    # 1. Identity & Core rules
    if receptionist.get("identity"):
        system_parts.append(receptionist["identity"])
    if receptionist.get("rules"):
        system_parts.append("Quy định hoạt động:\n" + "\n".join(f"- {r}" for r in receptionist["rules"]))

    # 2. Booking rules
    booking_parts = []
    if booking.get("rooms_info"):
        booking_parts.append("Thông tin các loại phòng:\n" + "\n".join(f"  {r}" for r in booking["rooms_info"]))
    if booking.get("rules"):
        booking_parts.append("Quy định đặt phòng:\n" + "\n".join(f"  {r}" for r in booking["rules"]))
    if booking_parts:
        system_parts.append("Về đặt phòng (booking_inquiry):\n" + "\n".join(booking_parts))

    # 3. FAQ & Intent rules
    if faq.get("rules"):
        system_parts.append("Về FAQ và phân loại Intent:\n" + "\n".join(f"- {r}" for r in faq["rules"]))

    # 4. Few-shot examples
    if fewshot:
        fewshot_parts = []
        for i, example in enumerate(fewshot, 1):
            fewshot_parts.append(
                f"Ví dụ {i}:\n"
                f"Khách: {example.get('user')}\n"
                f"AI Trả về JSON: {json.dumps(example.get('assistant'), ensure_ascii=False, indent=2)}"
            )
        system_parts.append("Các ví dụ mẫu để bạn học theo (Few-shot Examples):\n" + "\n\n".join(fewshot_parts))

    system_prompt = "\n\n".join(system_parts)

    return OpenAIConversationResponder(
        api_key=settings.openai_api_key,
        model=settings.response_model,
        timeout_seconds=settings.openai_request_timeout_seconds,
        system_prompt_template=system_prompt,
        timezone_name=settings.app_timezone,
    )


async def get_calendar_gateway(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CalendarGateway:
    if (
        settings.app_env == "test"
        or not settings.google_calendar_id
        or not settings.google_service_account_info
    ):
        return _calendar_gateway
    try:
        return GoogleCalendarAdapter(
            calendar_id=settings.google_calendar_id,
            service_account_info=settings.google_service_account_info,
        )
    except Exception:
        return _calendar_gateway


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
    room_repository: Annotated[RoomRepository, Depends(get_room_repository)],
    booking_repository: Annotated[BookingRepository, Depends(get_booking_repository)],
    calendar_gateway: Annotated[CalendarGateway, Depends(get_calendar_gateway)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProcessIncomingMessage:
    prompts = load_prompts()
    use_case_prompts = prompts["system"].get("booking", {}).get("use_cases", {})
    return ProcessIncomingMessage(
        ai_responder=ai_responder,
        conversation_repository=conversation_repository,
        idempotency_store=idempotency_store,
        message_gateway=message_gateway,
        escalation_notifier=escalation_notifier,
        room_repository=room_repository,
        booking_repository=booking_repository,
        calendar_gateway=calendar_gateway,
        history_limit=settings.ai_max_conversation_history,
        idempotency_ttl_seconds=settings.redis_idempotency_ttl_seconds,
        escalation_threshold=settings.ai_escalation_confidence_threshold,
        prompts=use_case_prompts,
    )
