import uuid
from collections.abc import Sequence
from typing import Protocol

from app.domain.booking import Booking, Room
from app.domain.messaging import (
    AIDecision,
    ConversationMessage,
    EscalationNotice,
    IncomingMessage,
)


class AIResponder(Protocol):
    async def analyze(
        self,
        message: IncomingMessage,
        history: Sequence[ConversationMessage],
    ) -> AIDecision: ...


class ConversationRepository(Protocol):
    async def get_recent(
        self,
        sender_id: str,
        limit: int,
    ) -> Sequence[ConversationMessage]: ...

    async def append_incoming(self, message: IncomingMessage) -> None: ...

    async def append_bot_reply(self, sender_id: str, text: str) -> None: ...

    async def get_conversation_id(self, sender_id: str) -> uuid.UUID | None: ...


class IdempotencyStore(Protocol):
    async def claim(self, event_id: str, ttl_seconds: int) -> bool: ...


class MessageGateway(Protocol):
    async def send_text(self, recipient_id: str, text: str) -> None: ...


class EscalationNotifier(Protocol):
    async def notify(self, notice: EscalationNotice) -> None: ...


class RoomRepository(Protocol):
    async def get_all(self) -> Sequence[Room]: ...
    async def get_by_name(self, name: str) -> Room | None: ...
    async def get_by_id(self, room_id: uuid.UUID) -> Room | None: ...


class BookingRepository(Protocol):
    async def create(self, booking: Booking) -> Booking: ...
    async def get_active_bookings_by_room(self, room_id: uuid.UUID) -> Sequence[Booking]: ...


from datetime import datetime


class CalendarGateway(Protocol):
    async def create_event(
        self,
        *,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str,
    ) -> str | None: ...
