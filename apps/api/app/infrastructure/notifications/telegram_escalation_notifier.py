import logging
import uuid
from datetime import UTC, datetime

import httpx
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ConversationModel, EscalationModel
from app.domain.messaging import EscalationNotice, EscalationReason
from app.domain.ports import EscalationNotifier

logger = logging.getLogger(__name__)


class TelegramEscalationNotifier(EscalationNotifier):
    def __init__(
        self,
        *,
        bot_token: SecretStr,
        chat_id: str,
        api_base_url: str,
        timeout_seconds: float,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._api_base_url = api_base_url
        self._timeout_seconds = timeout_seconds
        self._session_factory = session_factory

    def _mask_psid(self, psid: str) -> str:
        if len(psid) <= 8:
            return "***"
        return f"{psid[:4]}...{psid[-4:]}"

    def _get_reason_vietnamese(self, reason: EscalationReason) -> str:
        match reason:
            case EscalationReason.BOOKING_REQUIRES_CONFIRMATION:
                return "Khách hàng muốn đặt phòng (cần chủ nhà xác nhận)"
            case EscalationReason.CUSTOMER_REQUESTED_HUMAN:
                return "Khách hàng yêu cầu gặp nhân viên trực tiếp"
            case EscalationReason.LOW_AI_CONFIDENCE:
                return "Độ tin cậy của AI thấp dưới ngưỡng cho phép"
            case EscalationReason.AI_PROVIDER_FAILURE:
                return "Lỗi kết nối dịch vụ AI (OpenAI API)"
            case _:
                return "Yêu cầu hỗ trợ từ con người"

    async def notify(self, notice: EscalationNotice) -> None:
        conversation_id = None
        try:
            async with self._session_factory() as session:
                stmt = select(ConversationModel.id).where(
                    ConversationModel.external_user_id == notice.sender_id,
                    ConversationModel.channel == "facebook",
                )
                result = await session.execute(stmt)
                conversation_id = result.scalar_one_or_none()
        except Exception as error:
            logger.error("Failed to query conversation for escalation log: %s", error)

        masked_psid = self._mask_psid(notice.sender_id)
        reason_vn = self._get_reason_vietnamese(notice.reason)

        message_text = (
            f"⚠️ <b>CẦN CAN THIỆP (ESCALATION)</b>\n"
            f"👤 <b>Khách hàng (PSID):</b> <code>{masked_psid}</code>\n"
            f"🏷️ <b>Lý do:</b> {reason_vn}\n"
            f"📝 <b>Tóm tắt nội dung:</b> {notice.summary}"
        )

        token_val = self._bot_token.get_secret_value()
        if not token_val or not self._chat_id:
            logger.warning(
                "Telegram Bot Token or Chat ID is not configured. Skipping notification."
            )
            if conversation_id:
                await self._log_escalation(
                    conversation_id=conversation_id,
                    reason=notice.reason.value,
                    summary=notice.summary,
                    status="failed",
                    telegram_message_id=None,
                )
            return

        url = f"{self._api_base_url}/bot{token_val}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": message_text,
            "parse_mode": "HTML",
        }

        status = "failed"
        telegram_message_id = None

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    status = "sent"
                    resp_data = response.json()
                    telegram_message_id = str(resp_data.get("result", {}).get("message_id"))
                else:
                    logger.error(
                        "Telegram API error status %d: %s", response.status_code, response.text
                    )
            except httpx.HTTPError as error:
                logger.error("Failed to send telegram notification: %s", error)

        if conversation_id:
            try:
                await self._log_escalation(
                    conversation_id=conversation_id,
                    reason=notice.reason.value,
                    summary=notice.summary,
                    status=status,
                    telegram_message_id=telegram_message_id,
                )
            except Exception as error:
                logger.error("Failed to save escalation log to DB: %s", error)

    async def _log_escalation(
        self,
        conversation_id: uuid.UUID,
        reason: str,
        summary: str,
        status: str,
        telegram_message_id: str | None,
    ) -> None:
        async with self._session_factory() as session:
            now_utc = datetime.now(UTC)
            escalation = EscalationModel(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                reason=reason,
                summary=summary,
                telegram_message_id=telegram_message_id,
                status=status,
                created_at=now_utc,
                updated_at=now_utc,
            )
            session.add(escalation)
            await session.commit()
