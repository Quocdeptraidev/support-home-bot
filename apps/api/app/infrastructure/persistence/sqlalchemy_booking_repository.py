import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookingModel
from app.domain.booking import Booking, BookingStatus
from app.domain.ports import BookingRepository


class SqlAlchemyBookingRepository(BookingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map_model_to_entity(self, model: BookingModel) -> Booking:
        return Booking(
            id=model.id,
            conversation_id=model.conversation_id,
            room_id=model.room_id,
            check_in=model.check_in,
            check_out=model.check_out,
            guest_count=model.guest_count,
            phone=model.phone,
            total_price=model.total_price,
            status=BookingStatus(model.status),
        )

    async def create(self, booking: Booking) -> Booking:
        now_utc = datetime.now(UTC)
        model = BookingModel(
            id=booking.id,
            conversation_id=booking.conversation_id,
            room_id=booking.room_id,
            check_in=booking.check_in,
            check_out=booking.check_out,
            guest_count=booking.guest_count,
            phone=booking.phone,
            total_price=booking.total_price,
            status=booking.status.value,
            created_at=now_utc,
            updated_at=now_utc,
        )
        self._session.add(model)
        entity = self._map_model_to_entity(model)
        await self._session.commit()
        return entity

    async def get_active_bookings_by_room(self, room_id: uuid.UUID) -> Sequence[Booking]:
        stmt = select(BookingModel).where(
            BookingModel.room_id == room_id,
            BookingModel.status != "canceled",
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._map_model_to_entity(m) for m in models]
