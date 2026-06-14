from collections.abc import Sequence
from datetime import UTC, datetime

from app.application.use_cases.process_incoming_message import ProcessIncomingMessage
from app.domain.messaging import (
    AIDecision,
    ConversationMessage,
    EscalationNotice,
    EscalationReason,
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


async def test_booking_confirmation_is_saved_replied_and_escalated() -> None:
    conversation_repository = FakeConversationRepository()
    message_gateway = FakeMessageGateway()
    notifier = FakeEscalationNotifier()
    message = IncomingMessage(
        event_id="event-1",
        message_id="message-1",
        sender_id="facebook-user-1",
        text="Chốt phòng này giúp mình",
        received_at=datetime.now(UTC),
    )
    use_case = ProcessIncomingMessage(
        ai_responder=FakeAIResponder(
            AIDecision(
                intent=Intent.BOOKING_CONFIRMATION,
                draft_reply="Dạ em đã chuyển thông tin cho chủ homestay xác nhận ạ.",
                confidence=0.98,
                needs_human=False,
            )
        ),
        conversation_repository=conversation_repository,
        idempotency_store=FakeIdempotencyStore(),
        message_gateway=message_gateway,
        escalation_notifier=notifier,
        history_limit=10,
        idempotency_ttl_seconds=86400,
        escalation_threshold=0.65,
    )

    result = await use_case.execute(message)

    assert result.reply_sent is True
    assert result.escalated is True
    assert conversation_repository.incoming == [message]
    assert message_gateway.sent == [
        (
            "facebook-user-1",
            "Dạ em đã chuyển thông tin cho chủ homestay xác nhận ạ.",
        )
    ]
    assert notifier.notices[0].reason is EscalationReason.BOOKING_REQUIRES_CONFIRMATION


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
