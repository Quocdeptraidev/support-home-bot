import logging
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_process_telegram_callback_use_case
from app.application.use_cases.process_telegram_callback import ProcessTelegramCallback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks/telegram", tags=["telegram"])


# Pydantic Schemas cho Telegram Webhook Payload
class TelegramChat(BaseModel):
    id: int


class TelegramMessage(BaseModel):
    message_id: int
    chat: TelegramChat
    text: str | None = None


class TelegramCallbackQuery(BaseModel):
    id: str
    message: TelegramMessage | None = None
    data: str


class TelegramUpdate(BaseModel):
    update_id: int
    callback_query: TelegramCallbackQuery | None = Field(default=None, alias="callback_query")


@router.post("")
async def receive_telegram_webhook(
    update: TelegramUpdate,
    use_case: Annotated[ProcessTelegramCallback, Depends(get_process_telegram_callback_use_case)],
) -> Any:
    """
    Nhận callback event từ Telegram bot khi chủ nhà bấm nút Xác nhận hoặc Hủy đặt phòng.
    """
    logger.info("Received Telegram webhook update ID: %d", update.update_id)

    if not update.callback_query:
        logger.info("Telegram update has no callback_query. Skipping.")
        return {"status": "skipped", "reason": "no_callback_query"}

    query = update.callback_query
    if not query.message:
        logger.warning("Telegram callback query has no message context. Query ID: %s", query.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Callback query must contain message context",
        )

    success = await use_case.execute(
        callback_query_id=query.id,
        chat_id=str(query.message.chat.id),
        message_id=str(query.message.message_id),
        message_text=query.message.text or "",
        callback_data=query.data,
    )

    if not success:
        return {"status": "failed"}

    return {"status": "ok"}
