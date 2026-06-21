import uuid
from collections import defaultdict
from collections.abc import Sequence

from app.domain.messaging import ConversationMessage, IncomingMessage, MessageRole
from app.domain.ports import ConversationRepository


class InMemoryConversationRepository(ConversationRepository):
    def __init__(self) -> None:
        self._store: dict[str, list[ConversationMessage]] = defaultdict(list)
        self._conv_to_user: dict[uuid.UUID, str] = {}

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

    async def get_conversation_id(self, sender_id: str) -> uuid.UUID | None:
        import uuid

        conv_id = uuid.uuid5(uuid.NAMESPACE_DNS, sender_id)
        self._conv_to_user[conv_id] = sender_id
        return conv_id

    async def get_external_user_id(self, conversation_id: uuid.UUID) -> str | None:
        return self._conv_to_user.get(conversation_id)
