import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RoomModel
from app.domain.booking import Room
from app.domain.ports import RoomRepository


class SqlAlchemyRoomRepository(RoomRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map_model_to_entity(self, model: RoomModel) -> Room:
        return Room(
            id=model.id,
            name=model.name,
            price_per_night=model.price_per_night,
            price_per_hour=model.price_per_hour,
            capacity=model.capacity,
        )

    async def get_all(self) -> Sequence[Room]:
        stmt = select(RoomModel)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._map_model_to_entity(m) for m in models]

    async def get_by_name(self, name: str) -> Room | None:
        # Case insensitive match
        stmt = select(RoomModel).where(RoomModel.name.ilike(name))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._map_model_to_entity(model)

    async def get_by_id(self, room_id: uuid.UUID) -> Room | None:
        stmt = select(RoomModel).where(RoomModel.id == room_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._map_model_to_entity(model)
