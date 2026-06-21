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
                name="Home 1",
                price_per_night=600000,
                price_per_hour=100000,
                capacity=2,
            ),
            uuid.UUID("22222222-2222-2222-2222-222222222222"): Room(
                id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                name="Home 2",
                price_per_night=500000,
                price_per_hour=80000,
                capacity=2,
            ),
            uuid.UUID("33333333-3333-3333-3333-333333333333"): Room(
                id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                name="Home 3",
                price_per_night=400000,
                price_per_hour=60000,
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
