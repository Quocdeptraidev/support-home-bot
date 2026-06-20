import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationModel, MessageModel
from app.domain.messaging import ConversationMessage, IncomingMessage, MessageRole
from app.domain.ports import ConversationRepository


class SqlAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_recent(
        self,
        sender_id: str,
        limit: int,
    ) -> Sequence[ConversationMessage]:
        stmt_conv = select(ConversationModel).where(
            ConversationModel.external_user_id == sender_id,
            ConversationModel.channel == "facebook",
        )
        result_conv = await self._session.execute(stmt_conv)
        conv = result_conv.scalar_one_or_none()
        if not conv:
            return []

        stmt_msg = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conv.id)
            .order_by(MessageModel.created_at.desc())
            .limit(limit)
        )
        result_msg = await self._session.execute(stmt_msg)
        msgs = result_msg.scalars().all()

        def map_role(db_sender: str) -> MessageRole:
            match db_sender:
                case "customer":
                    return MessageRole.CUSTOMER
                case "bot":
                    return MessageRole.BOT
                case "human":
                    return MessageRole.HUMAN
                case _:
                    return MessageRole.CUSTOMER

        return [ConversationMessage(role=map_role(m.sender), text=m.text) for m in reversed(msgs)]

    async def append_incoming(self, message: IncomingMessage) -> None:
        stmt_conv = select(ConversationModel).where(
            ConversationModel.external_user_id == message.sender_id,
            ConversationModel.channel == "facebook",
        )
        result_conv = await self._session.execute(stmt_conv)
        conv = result_conv.scalar_one_or_none()

        now_utc = datetime.now(UTC)
        if not conv:
            conv = ConversationModel(
                id=uuid.uuid4(),
                channel="facebook",
                external_user_id=message.sender_id,
                status="bot_active",
                last_message_at=message.received_at,
                created_at=now_utc,
                updated_at=now_utc,
            )
            self._session.add(conv)
        else:
            conv.last_message_at = message.received_at
            conv.updated_at = now_utc

        msg = MessageModel(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            external_message_id=message.message_id,
            direction="inbound",
            sender="customer",
            text=message.text,
            provider_payload={},
            delivery_status="received",
            created_at=message.received_at,
            updated_at=now_utc,
        )
        self._session.add(msg)
        await self._session.commit()

    async def append_bot_reply(self, sender_id: str, text: str) -> None:
        stmt_conv = select(ConversationModel).where(
            ConversationModel.external_user_id == sender_id,
            ConversationModel.channel == "facebook",
        )
        result_conv = await self._session.execute(stmt_conv)
        conv = result_conv.scalar_one_or_none()

        now_utc = datetime.now(UTC)
        if not conv:
            conv = ConversationModel(
                id=uuid.uuid4(),
                channel="facebook",
                external_user_id=sender_id,
                status="bot_active",
                last_message_at=now_utc,
                created_at=now_utc,
                updated_at=now_utc,
            )
            self._session.add(conv)
        else:
            conv.last_message_at = now_utc
            conv.updated_at = now_utc

        msg = MessageModel(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            external_message_id=None,
            direction="outbound",
            sender="bot",
            text=text,
            provider_payload={},
            delivery_status="sent",
            created_at=now_utc,
            updated_at=now_utc,
        )
        self._session.add(msg)
        await self._session.commit()

    async def get_conversation_id(self, sender_id: str) -> uuid.UUID | None:
        stmt = select(ConversationModel.id).where(
            ConversationModel.external_user_id == sender_id,
            ConversationModel.channel == "facebook",
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
