from collections.abc import Sequence

from app.domain.messaging import (
    AIDecision,
    ConversationMessage,
    ExtractedEntities,
    IncomingMessage,
    Intent,
)
from app.domain.ports import AIResponder


class FakeAIResponder(AIResponder):
    def __init__(
        self,
        default_reply: str = "Dạ chào anh/chị, em có thể giúp gì cho mình ạ?",
    ) -> None:
        self._default_reply = default_reply

    async def analyze(
        self,
        message: IncomingMessage,
        history: Sequence[ConversationMessage],
    ) -> AIDecision:
        text = message.text.lower()
        if "giá phòng" in text or "mấy giờ" in text or "check in" in text:
            return AIDecision(
                intent=Intent.FAQ,
                draft_reply=(
                    "Dạ homestay bên em nhận phòng từ 14h và trả phòng trước 12h ngày hôm sau ạ. "
                    "Giá phòng tuỳ loại từ 650.000đ/đêm ạ."
                ),
                confidence=0.95,
                needs_human=False,
            )
        elif "chốt" in text or "đặt phòng" in text:
            return AIDecision(
                intent=Intent.BOOKING_CONFIRMATION,
                draft_reply=(
                    "Dạ em đã nhận thông tin đặt phòng của mình và đang chuyển "
                    "cho chủ nhà xác nhận ạ."
                ),
                confidence=0.98,
                needs_human=False,
                entities=ExtractedEntities(guest_count=2),
            )
        elif "gặp nhân viên" in text or "gặp chủ nhà" in text:
            return AIDecision(
                intent=Intent.HUMAN_REQUEST,
                draft_reply=(
                    "Dạ em xin lỗi, em đang chuyển kết nối cuộc trò chuyện cho "
                    "nhân viên hỗ trợ trực tiếp mình ngay ạ."
                ),
                confidence=0.99,
                needs_human=True,
            )
        elif "không chắc" in text or "mông lung" in text:
            return AIDecision(
                intent=Intent.UNKNOWN,
                draft_reply="Dạ em chưa rõ ý mình lắm ạ.",
                confidence=0.3,
                needs_human=False,
            )
        else:
            return AIDecision(
                intent=Intent.UNKNOWN,
                draft_reply=self._default_reply,
                confidence=0.8,
                needs_human=False,
            )
