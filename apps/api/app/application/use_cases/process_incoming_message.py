from app.application.errors import AIProviderError
from app.domain.messaging import (
    AIDecision,
    EscalationNotice,
    EscalationReason,
    IncomingMessage,
    Intent,
    ProcessMessageResult,
)
from app.domain.ports import (
    AIResponder,
    ConversationRepository,
    EscalationNotifier,
    IdempotencyStore,
    MessageGateway,
)

FALLBACK_REPLY = "Dạ em đã nhận được tin nhắn. Chủ homestay sẽ phản hồi mình sớm nhất có thể ạ."


class ProcessIncomingMessage:
    def __init__(
        self,
        *,
        ai_responder: AIResponder,
        conversation_repository: ConversationRepository,
        idempotency_store: IdempotencyStore,
        message_gateway: MessageGateway,
        escalation_notifier: EscalationNotifier,
        history_limit: int,
        idempotency_ttl_seconds: int,
        escalation_threshold: float,
    ) -> None:
        self._ai_responder = ai_responder
        self._conversation_repository = conversation_repository
        self._idempotency_store = idempotency_store
        self._message_gateway = message_gateway
        self._escalation_notifier = escalation_notifier
        self._history_limit = history_limit
        self._idempotency_ttl_seconds = idempotency_ttl_seconds
        self._escalation_threshold = escalation_threshold

    async def execute(self, message: IncomingMessage) -> ProcessMessageResult:
        claimed = await self._idempotency_store.claim(
            message.event_id,
            self._idempotency_ttl_seconds,
        )
        if not claimed:
            return ProcessMessageResult(duplicate=True, reply_sent=False, escalated=False)

        history = await self._conversation_repository.get_recent(
            message.sender_id,
            self._history_limit,
        )
        await self._conversation_repository.append_incoming(message)

        try:
            decision = await self._ai_responder.analyze(message, history)
        except AIProviderError:
            decision = AIDecision(
                intent=Intent.UNKNOWN,
                draft_reply=FALLBACK_REPLY,
                confidence=0,
                needs_human=True,
                escalation_reason=EscalationReason.AI_PROVIDER_FAILURE,
            )

        reply = decision.draft_reply.strip() or FALLBACK_REPLY
        await self._message_gateway.send_text(message.sender_id, reply)
        await self._conversation_repository.append_bot_reply(message.sender_id, reply)

        is_booking_confirmation = decision.intent is Intent.BOOKING_CONFIRMATION
        should_escalate = (
            is_booking_confirmation
            or decision.needs_human
            or decision.confidence < self._escalation_threshold
        )
        if should_escalate:
            if decision.escalation_reason is not None:
                reason = decision.escalation_reason
            elif is_booking_confirmation:
                reason = EscalationReason.BOOKING_REQUIRES_CONFIRMATION
            else:
                reason = EscalationReason.LOW_AI_CONFIDENCE
            await self._escalation_notifier.notify(
                EscalationNotice(
                    sender_id=message.sender_id,
                    reason=reason,
                    summary=message.text,
                )
            )

        return ProcessMessageResult(
            duplicate=False,
            reply_sent=True,
            escalated=should_escalate,
        )
