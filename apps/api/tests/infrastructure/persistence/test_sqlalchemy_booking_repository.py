import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.models import ConversationModel
from app.domain.booking import Booking, BookingStatus
from app.infrastructure.persistence.sqlalchemy_booking_repository import (
    SqlAlchemyBookingRepository,
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
async def test_sqlalchemy_booking_repo_create_and_get_active(db_session: AsyncSession) -> None:
    # 1. Create a Conversation in DB
    conv_id = uuid.uuid4()
    now_utc = datetime.now(UTC)
    conv = ConversationModel(
        id=conv_id,
        channel="facebook",
        external_user_id="user-123456",
        status="bot_active",
        created_at=now_utc,
        updated_at=now_utc,
    )
    db_session.add(conv)
    await db_session.commit()

    # 2. Use a seeded room ID (Couple View Vườn ID: 11111111-1111-1111-1111-111111111111)
    room_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    repo = SqlAlchemyBookingRepository(db_session)

    # 3. Create a Booking
    booking = Booking(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        room_id=room_id,
        check_in=date(2026, 6, 20),
        check_out=date(2026, 6, 22),
        guest_count=2,
        phone="0909123456",
        total_price=1300000,
        status=BookingStatus.PENDING,
    )
    saved = await repo.create(booking)
    assert saved.id == booking.id
    assert saved.status == BookingStatus.PENDING

    # 4. Query active bookings
    active = await repo.get_active_bookings_by_room(room_id)
    assert len(active) == 1
    assert active[0].id == booking.id
    assert active[0].status == BookingStatus.PENDING

    # 5. Create a canceled booking and ensure it doesn't show up in active list
    canceled_booking = Booking(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        room_id=room_id,
        check_in=date(2026, 6, 25),
        check_out=date(2026, 6, 27),
        guest_count=2,
        phone="0909123456",
        total_price=1300000,
        status=BookingStatus.CANCELED,
    )
    await repo.create(canceled_booking)

    active_after = await repo.get_active_bookings_by_room(room_id)
    # Canceled booking should NOT be returned
    assert len(active_after) == 1
    assert active_after[0].id == booking.id
