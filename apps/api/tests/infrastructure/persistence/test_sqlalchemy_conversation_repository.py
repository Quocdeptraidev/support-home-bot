from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.models import ConversationModel, MessageModel
from app.domain.messaging import IncomingMessage, MessageRole
from app.infrastructure.persistence.sqlalchemy_conversation_repository import (
    SqlAlchemyConversationRepository,
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


@pytest.mark.asyncio
async def test_sqlalchemy_repo_append_incoming_and_get_recent(db_session: AsyncSession) -> None:
    repo = SqlAlchemyConversationRepository(db_session)
    sender_id = "fb-user-123"

    # 1. Thêm tin nhắn đến thứ nhất
    msg1 = IncomingMessage(
        event_id="evt-1",
        message_id="mid-1",
        sender_id=sender_id,
        text="Xin chào, tôi muốn hỏi giá phòng",
        received_at=datetime.now(UTC),
    )
    await repo.append_incoming(msg1)

    # Kiểm tra trong DB xem conversation đã được tạo
    stmt_conv = select(ConversationModel).where(
        ConversationModel.external_user_id == sender_id,
        ConversationModel.channel == "facebook",
    )
    conv = (await db_session.execute(stmt_conv)).scalar_one_or_none()
    assert conv is not None
    assert conv.status == "bot_active"

    # Kiểm tra tin nhắn trong DB
    stmt_msg = select(MessageModel).where(MessageModel.conversation_id == conv.id)
    msgs_db = (await db_session.execute(stmt_msg)).scalars().all()
    assert len(msgs_db) == 1
    assert msgs_db[0].text == "Xin chào, tôi muốn hỏi giá phòng"
    assert msgs_db[0].direction == "inbound"
    assert msgs_db[0].sender == "customer"

    # 2. Thêm tin nhắn bot reply
    await repo.append_bot_reply(sender_id, "Dạ giá phòng bên em từ 650k ạ.")

    # 3. Thêm tin nhắn đến thứ hai
    msg2 = IncomingMessage(
        event_id="evt-2",
        message_id="mid-2",
        sender_id=sender_id,
        text="Có phòng view vườn không?",
        received_at=datetime.now(UTC),
    )
    await repo.append_incoming(msg2)

    # 4. Lấy lịch sử tin nhắn gần đây
    history = await repo.get_recent(sender_id, limit=10)
    assert len(history) == 3
    assert history[0].role == MessageRole.CUSTOMER
    assert history[0].text == "Xin chào, tôi muốn hỏi giá phòng"
    assert history[1].role == MessageRole.BOT
    assert history[1].text == "Dạ giá phòng bên em từ 650k ạ."
    assert history[2].role == MessageRole.CUSTOMER
    assert history[2].text == "Có phòng view vườn không?"

    # Kiểm tra giới hạn limit
    history_limit = await repo.get_recent(sender_id, limit=2)
    assert len(history_limit) == 2
    assert history_limit[0].role == MessageRole.BOT
    assert history_limit[1].role == MessageRole.CUSTOMER
