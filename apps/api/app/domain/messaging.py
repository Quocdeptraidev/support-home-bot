from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class MessageRole(StrEnum):
    CUSTOMER = "customer"
    BOT = "bot"
    HUMAN = "human"


class Intent(StrEnum):
    FAQ = "faq"
    BOOKING_INQUIRY = "booking_inquiry"
    BOOKING_CONFIRMATION = "booking_confirmation"
    HUMAN_REQUEST = "human_request"
    UNKNOWN = "unknown"


class EscalationReason(StrEnum):
    BOOKING_REQUIRES_CONFIRMATION = "booking_requires_confirmation"
    CUSTOMER_REQUESTED_HUMAN = "customer_requested_human"
    LOW_AI_CONFIDENCE = "low_ai_confidence"
    AI_PROVIDER_FAILURE = "ai_provider_failure"


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    event_id: str
    message_id: str
    sender_id: str
    text: str
    received_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: MessageRole
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedEntities:
    check_in: datetime | None = None
    check_out: datetime | None = None
    guest_count: int | None = None
    phone: str | None = None
    room_name: str | None = None

    def __post_init__(self) -> None:
        if self.guest_count is not None and self.guest_count < 1:
            raise ValueError("guest_count must be greater than zero")
        if (
            self.check_in is not None
            and self.check_out is not None
            and self.check_out <= self.check_in
        ):
            raise ValueError("check_out must be after check_in")


@dataclass(frozen=True, slots=True)
class AIDecision:
    intent: Intent
    draft_reply: str
    confidence: float
    needs_human: bool
    entities: ExtractedEntities = field(default_factory=ExtractedEntities)
    escalation_reason: EscalationReason | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EscalationNotice:
    sender_id: str
    reason: EscalationReason
    summary: str


@dataclass(frozen=True, slots=True)
class ProcessMessageResult:
    duplicate: bool
    reply_sent: bool
    escalated: bool
