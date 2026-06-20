import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

from app.application.use_cases.process_incoming_message import ProcessIncomingMessage
from app.domain.booking import Booking, BookingStatus, Room
from app.domain.messaging import (
    AIDecision,
    ConversationMessage,
    EscalationNotice,
    EscalationReason,
    ExtractedEntities,
    IncomingMessage,
    Intent,
)


class FakeAIResponder:
    def __init__(self, decision: AIDecision) -> None:
        self.decision = decision

    async def analyze(
        self,
        message: IncomingMessage,
        history: Sequence[ConversationMessage],
    ) -> AIDecision:
        return self.decision


class FakeConversationRepository:
    def __init__(self) -> None:
        self.incoming: list[IncomingMessage] = []
        self.bot_replies: list[tuple[str, str]] = []

    async def get_recent(
        self,
        sender_id: str,
        limit: int,
    ) -> Sequence[ConversationMessage]:
        return []

    async def append_incoming(self, message: IncomingMessage) -> None:
        self.incoming.append(message)

    async def append_bot_reply(self, sender_id: str, text: str) -> None:
        self.bot_replies.append((sender_id, text))

    async def get_conversation_id(self, sender_id: str) -> uuid.UUID | None:
        return uuid.uuid5(uuid.NAMESPACE_DNS, sender_id)


class FakeIdempotencyStore:
    def __init__(self, claimed: bool = True) -> None:
        self.claimed = claimed

    async def claim(self, event_id: str, ttl_seconds: int) -> bool:
        return self.claimed


class FakeMessageGateway:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_text(self, recipient_id: str, text: str) -> None:
        self.sent.append((recipient_id, text))


class FakeEscalationNotifier:
    def __init__(self) -> None:
        self.notices: list[EscalationNotice] = []

    async def notify(self, notice: EscalationNotice) -> None:
        self.notices.append(notice)


class FakeRoomRepository:
    def __init__(self, rooms: list[Room] | None = None) -> None:
        self.rooms = rooms or []

    async def get_all(self) -> Sequence[Room]:
        return self.rooms

    async def get_by_name(self, name: str) -> Room | None:
        for r in self.rooms:
            if r.name.lower() == name.lower():
                return r
        return None

    async def get_by_id(self, room_id: uuid.UUID) -> Room | None:
        for r in self.rooms:
            if r.id == room_id:
                return r
        return None


class FakeBookingRepository:
    def __init__(self, bookings: list[Booking] | None = None) -> None:
        self.bookings = bookings or []

    async def create(self, booking: Booking) -> Booking:
        self.bookings.append(booking)
        return booking

    async def get_active_bookings_by_room(self, room_id: uuid.UUID) -> Sequence[Booking]:
        return [
            b for b in self.bookings if b.room_id == room_id and b.status != BookingStatus.CANCELED
        ]


async def test_booking_confirmation_is_saved_replied_and_escalated() -> None:
    conversation_repository = FakeConversationRepository()
    message_gateway = FakeMessageGateway()
    notifier = FakeEscalationNotifier()

    room_id = uuid.uuid4()
    room = Room(id=room_id, name="Couple View Vườn", price_per_night=650000, capacity=2)
    room_repository = FakeRoomRepository([room])
    booking_repository = FakeBookingRepository([])

    message = IncomingMessage(
        event_id="event-1",
        message_id="message-1",
        sender_id="facebook-user-1",
        text="Chốt phòng này giúp mình nhé",
        received_at=datetime.now(UTC),
    )
    use_case = ProcessIncomingMessage(
        ai_responder=FakeAIResponder(
            AIDecision(
                intent=Intent.BOOKING_CONFIRMATION,
                draft_reply="Dạ em đã chuyển thông tin cho chủ homestay xác nhận ạ.",
                confidence=0.98,
                needs_human=False,
                entities=ExtractedEntities(
                    check_in=date(2026, 6, 20),
                    check_out=date(2026, 6, 22),
                    guest_count=2,
                    phone="0909123456",
                    room_name="Couple View Vườn",
                ),
            )
        ),
        conversation_repository=conversation_repository,
        idempotency_store=FakeIdempotencyStore(),
        message_gateway=message_gateway,
        escalation_notifier=notifier,
        room_repository=room_repository,
        booking_repository=booking_repository,
        history_limit=10,
        idempotency_ttl_seconds=86400,
        escalation_threshold=0.65,
    )

    result = await use_case.execute(message)

    assert result.reply_sent is True
    assert result.escalated is True
    assert conversation_repository.incoming == [message]
    # Check that the reply was overridden by the deterministic business rule
    assert "Dạ em đã ghi nhận thông tin đặt phòng Couple View Vườn" in message_gateway.sent[0][1]
    assert "0909123456" in message_gateway.sent[0][1]
    assert notifier.notices[0].reason is EscalationReason.BOOKING_REQUIRES_CONFIRMATION
    assert len(booking_repository.bookings) == 1
    assert booking_repository.bookings[0].status == BookingStatus.PENDING
    assert booking_repository.bookings[0].total_price == 1300000


async def test_booking_inquiry_shows_available_rooms() -> None:
    conversation_repository = FakeConversationRepository()
    message_gateway = FakeMessageGateway()
    notifier = FakeEscalationNotifier()

    r1 = Room(id=uuid.uuid4(), name="Couple View Vườn", price_per_night=650000, capacity=2)
    r2 = Room(id=uuid.uuid4(), name="Family Valley View", price_per_night=1200000, capacity=4)
    room_repository = FakeRoomRepository([r1, r2])
    booking_repository = FakeBookingRepository([])

    message = IncomingMessage(
        event_id="event-1",
        message_id="message-1",
        sender_id="facebook-user-1",
        text="Ngày 20 đến 22 tháng 6 còn phòng cho 2 người không?",
        received_at=datetime.now(UTC),
    )
    use_case = ProcessIncomingMessage(
        ai_responder=FakeAIResponder(
            AIDecision(
                intent=Intent.BOOKING_INQUIRY,
                draft_reply="Dạ mình muốn đi ngày nào ạ?",
                confidence=0.95,
                needs_human=False,
                entities=ExtractedEntities(
                    check_in=date(2026, 6, 20),
                    check_out=date(2026, 6, 22),
                    guest_count=2,
                ),
            )
        ),
        conversation_repository=conversation_repository,
        idempotency_store=FakeIdempotencyStore(),
        message_gateway=message_gateway,
        escalation_notifier=notifier,
        room_repository=room_repository,
        booking_repository=booking_repository,
        history_limit=10,
        idempotency_ttl_seconds=86400,
        escalation_threshold=0.65,
    )

    result = await use_case.execute(message)
    assert result.reply_sent is True
    assert "Couple View Vườn" in message_gateway.sent[0][1]
    assert "Family Valley View" in message_gateway.sent[0][1]


async def test_duplicate_event_has_no_side_effect() -> None:
    conversation_repository = FakeConversationRepository()
    message_gateway = FakeMessageGateway()
    notifier = FakeEscalationNotifier()
    use_case = ProcessIncomingMessage(
        ai_responder=FakeAIResponder(
            AIDecision(
                intent=Intent.FAQ,
                draft_reply="Dạ homestay nhận phòng từ 14 giờ ạ.",
                confidence=0.99,
                needs_human=False,
            )
        ),
        conversation_repository=conversation_repository,
        idempotency_store=FakeIdempotencyStore(claimed=False),
        message_gateway=message_gateway,
        escalation_notifier=notifier,
        room_repository=FakeRoomRepository(),
        booking_repository=FakeBookingRepository(),
        history_limit=10,
        idempotency_ttl_seconds=86400,
        escalation_threshold=0.65,
    )

    result = await use_case.execute(
        IncomingMessage(
            event_id="duplicate-event",
            message_id="duplicate-message",
            sender_id="facebook-user-1",
            text="Mấy giờ nhận phòng?",
            received_at=datetime.now(UTC),
        )
    )

    assert result.duplicate is True
    assert conversation_repository.incoming == []
    assert message_gateway.sent == []
    assert notifier.notices == []
