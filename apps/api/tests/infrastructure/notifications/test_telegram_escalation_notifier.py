import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.models import ConversationModel, EscalationModel
from app.domain.messaging import EscalationNotice, EscalationReason
from app.infrastructure.notifications.telegram_escalation_notifier import (
    TelegramEscalationNotifier,
)


@pytest.fixture
async def db_session() -> AsyncSession:
    settings = Settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    connection = await engine.connect()
    transaction = await connection.begin()

    session = AsyncSession(bind=connection)

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()
    await engine.dispose()


@pytest.fixture
def session_factory(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    # Mock session factory trả về session hiện tại đang chạy trong test transaction.
    class FakeFactory:
        def __init__(self, s: AsyncSession) -> None:
            self._s = s

        async def __aenter__(self) -> AsyncSession:
            return self._s

        async def __aexit__(self, exc_type: type, exc_val: Exception, exc_tb: Any) -> None:
            pass

        def __call__(self) -> "FakeFactory":
            return self

    return FakeFactory(db_session)  # type: ignore


@respx.mock
@pytest.mark.asyncio
async def test_telegram_notifier_success(
    respx_mock: respx.MockRouter,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # 1. Tạo conversation trước để liên kết khóa ngoại
    conv_id = uuid.uuid4()
    conv = ConversationModel(
        id=conv_id,
        channel="facebook",
        external_user_id="customer-123456789",
        status="bot_active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(conv)
    await db_session.commit()

    # 2. Mock Telegram API
    bot_token = "my-bot-token"
    chat_id = "my-chat-id"
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    telegram_route = respx_mock.post(telegram_url).mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 9999}})
    )

    notifier = TelegramEscalationNotifier(
        bot_token=SecretStr(bot_token),
        chat_id=chat_id,
        api_base_url="https://api.telegram.org",
        timeout_seconds=10.0,
        session_factory=session_factory,
    )

    # 3. Gửi notification
    notice = EscalationNotice(
        sender_id="customer-123456789",
        reason=EscalationReason.LOW_AI_CONFIDENCE,
        summary="Cần phòng giá bao nhiêu ạ?",
    )
    await notifier.notify(notice)

    # Kiểm tra xem Telegram API đã được gọi đúng tham số
    assert telegram_route.called
    req_body = telegram_route.calls.last.request.read().decode()
    assert "customer-123456789" not in req_body  # ID đã bị che bớt
    assert "cust...8789" in req_body or "cust...9" in req_body or "cust" in req_body
    assert "Độ tin cậy của AI thấp" in req_body

    # Kiểm tra log trong DB
    stmt_esc = select(EscalationModel).where(EscalationModel.conversation_id == conv_id)
    esc = (await db_session.execute(stmt_esc)).scalar_one_or_none()
    assert esc is not None
    assert esc.status == "sent"
    assert esc.telegram_message_id == "9999"
    assert esc.reason == "low_ai_confidence"
    assert esc.summary == "Cần phòng giá bao nhiêu ạ?"
