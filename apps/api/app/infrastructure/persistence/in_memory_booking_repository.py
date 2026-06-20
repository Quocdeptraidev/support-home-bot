import uuid
from collections.abc import Sequence

from app.domain.booking import Booking, BookingStatus
from app.domain.ports import BookingRepository


class InMemoryBookingRepository(BookingRepository):
    def __init__(self) -> None:
        self._bookings: dict[uuid.UUID, Booking] = {}

    async def create(self, booking: Booking) -> Booking:
        self._bookings[booking.id] = booking
        return booking

    async def get_active_bookings_by_room(self, room_id: uuid.UUID) -> Sequence[Booking]:
        return [
            b
            for b in self._bookings.values()
            if b.room_id == room_id and b.status != BookingStatus.CANCELED
        ]
