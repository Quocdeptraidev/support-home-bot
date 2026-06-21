import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.infrastructure.persistence.sqlalchemy_room_repository import (
    SqlAlchemyRoomRepository,
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
async def test_sqlalchemy_room_repo_get_all_and_get_by_name(db_session: AsyncSession) -> None:
    repo = SqlAlchemyRoomRepository(db_session)

    # Test get_all (should find the seeded rooms: Home 1, Home 2, Home 3)
    rooms = await repo.get_all()
    assert len(rooms) >= 3
    room_names = [r.name for r in rooms]
    assert "Home 1" in room_names
    assert "Home 2" in room_names
    assert "Home 3" in room_names

    # Test get_by_name (case-insensitive)
    r1 = await repo.get_by_name("home 1")
    assert r1 is not None
    assert r1.price_per_night == 600000
    assert r1.price_per_hour == 100000
    assert r1.capacity == 2

    # Test get_by_id
    r2 = await repo.get_by_id(uuid.UUID("11111111-1111-1111-1111-111111111111"))
    assert r2 is not None
    assert r2.name == "Home 1"

    # Test not found
    assert await repo.get_by_name("Non-existent room") is None
    assert await repo.get_by_id(uuid.uuid4()) is None
