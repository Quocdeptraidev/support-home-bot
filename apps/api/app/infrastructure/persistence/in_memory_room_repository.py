import uuid
from collections.abc import Sequence

from app.domain.booking import Room
from app.domain.ports import RoomRepository


class InMemoryRoomRepository(RoomRepository):
    def __init__(self) -> None:
        # Seed default rooms for tests, matching Alembic seed
        self._rooms = {
            uuid.UUID("11111111-1111-1111-1111-111111111111"): Room(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                name="Couple View Vườn",
                price_per_night=650000,
                capacity=2,
            ),
            uuid.UUID("22222222-2222-2222-2222-222222222222"): Room(
                id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                name="Family Valley View",
                price_per_night=1200000,
                capacity=4,
            ),
            uuid.UUID("33333333-3333-3333-3333-333333333333"): Room(
                id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                name="Standard Room",
                price_per_night=500000,
                capacity=2,
            ),
        }

    async def get_all(self) -> Sequence[Room]:
        return list(self._rooms.values())

    async def get_by_name(self, name: str) -> Room | None:
        for r in self._rooms.values():
            if r.name.lower() == name.lower():
                return r
        return None

    async def get_by_id(self, room_id: uuid.UUID) -> Room | None:
        return self._rooms.get(room_id)
