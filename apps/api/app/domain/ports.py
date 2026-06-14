from collections.abc import Sequence
from typing import Protocol

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


class IdempotencyStore(Protocol):
    async def claim(self, event_id: str, ttl_seconds: int) -> bool: ...


class MessageGateway(Protocol):
    async def send_text(self, recipient_id: str, text: str) -> None: ...


class EscalationNotifier(Protocol):
    async def notify(self, notice: EscalationNotice) -> None: ...
