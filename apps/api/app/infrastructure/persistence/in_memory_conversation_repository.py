from collections import defaultdict
from collections.abc import Sequence

from app.domain.messaging import ConversationMessage, IncomingMessage, MessageRole
from app.domain.ports import ConversationRepository


class InMemoryConversationRepository(ConversationRepository):
    def __init__(self) -> None:
        self._store: dict[str, list[ConversationMessage]] = defaultdict(list)

    async def get_recent(
        self,
        sender_id: str,
        limit: int,
    ) -> Sequence[ConversationMessage]:
        messages = self._store[sender_id]
        return messages[-limit:]

    async def append_incoming(self, message: IncomingMessage) -> None:
        conv_msg = ConversationMessage(
            role=MessageRole.CUSTOMER,
            text=message.text,
        )
        self._store[message.sender_id].append(conv_msg)

    async def append_bot_reply(self, sender_id: str, text: str) -> None:
        conv_msg = ConversationMessage(
            role=MessageRole.BOT,
            text=text,
        )
        self._store[sender_id].append(conv_msg)
