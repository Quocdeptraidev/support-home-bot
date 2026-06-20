import logging
from collections.abc import Sequence
from datetime import date, datetime

import dateparser  # type: ignore
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field, SecretStr

from app.application.errors import AIProviderError
from app.domain.messaging import (
    AIDecision,
    ConversationMessage,
    EscalationReason,
    ExtractedEntities,
    IncomingMessage,
    Intent,
    MessageRole,
)
from app.domain.ports import AIResponder

logger = logging.getLogger(__name__)


class OpenAIEntities(BaseModel):
    check_in: str | None = Field(
        default=None,
        description=(
            "Check-in date in YYYY-MM-DD format, parsed from user message relative to current time."
        ),
    )
    check_out: str | None = Field(
        default=None,
        description=(
            "Check-out date in YYYY-MM-DD format, parsed from user message relative "
            "to current time."
        ),
    )
    guest_count: int | None = Field(
        default=None,
        description="Number of guests, must be greater than zero.",
    )
    phone: str | None = Field(
        default=None,
        description="Customer phone number.",
    )
    room_name: str | None = Field(
        default=None,
        description="Requested room name.",
    )


class OpenAIResponseSchema(BaseModel):
    intent: Intent = Field(
        description=(
            "Classified intent of the user message (faq, booking_inquiry, "
            "booking_confirmation, human_request, unknown)."
        )
    )
    draft_reply: str = Field(
        description=(
            "Polite, warm, friendly draft response in Vietnamese. Always use "
            "polite particles ('dạ', 'ạ')."
        )
    )
    confidence: float = Field(
        description="Confidence level of classification and response, between 0.0 and 1.0."
    )
    needs_human: bool = Field(
        description="Whether this message requires manual intervention from human staff."
    )
    entities: OpenAIEntities = Field(
        default_factory=OpenAIEntities, description="Extracted entities from conversation."
    )
    escalation_reason: EscalationReason | None = Field(
        default=None,
        description="Reason for escalation if needs_human is true or confidence is low.",
    )


class OpenAIConversationResponder(AIResponder):
    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float,
        timezone_name: str = "Asia/Ho_Chi_Minh",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._timezone_name = timezone_name

        key_val = self._api_key.get_secret_value()
        if not key_val:
            raise AIProviderError("OpenAI API key is not configured")

        self._client = AsyncOpenAI(api_key=key_val)

    def _parse_date(self, date_str: str | None) -> date | None:
        if not date_str:
            return None
        try:
            parsed = dateparser.parse(date_str)
            if parsed:
                return parsed.date()  # type: ignore
        except Exception:
            pass

        try:
            return date.fromisoformat(date_str)
        except Exception:
            pass
        return None

    async def analyze(
        self,
        message: IncomingMessage,
        history: Sequence[ConversationMessage],
    ) -> AIDecision:
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        system_prompt = (
            "Bạn là một trợ lý ảo thông minh và thân thiện của Mây Homestay Đà Lạt "
            "(một homestay thơ mộng, ấm cúng).\n"
            "Nhiệm vụ của bạn là hỗ trợ khách hàng qua Messenger: trả lời câu hỏi FAQ "
            "và thu thập thông tin đặt phòng khi khách có nhu cầu.\n\n"
            "Quy định hoạt động:\n"
            "1. Bạn phải luôn trả lời bằng tiếng Việt lịch sự, ấm áp "
            "và sử dụng kính ngữ ('dạ', 'ạ').\n"
            f"2. Thời gian hiện tại hệ thống là: {current_time_str}. Hãy dùng mốc thời gian này "
            "để chuyển đổi các ngày tương đối (như 'thứ bảy tuần này', 'ngày mai', 'hôm nay') "
            "thành ngày cụ thể định dạng YYYY-MM-DD.\n"
            "3. Khi khách có ý định hỏi phòng hoặc đặt phòng (booking_inquiry):\n"
            "   - Hãy cố gắng thu thập các thông tin: check_in, check_out, guest_count, phone.\n"
            "   - Nếu thông tin nào chưa có, hãy phản hồi gợi ý một cách tự nhiên để hỏi thêm "
            "thông tin đó.\n"
            "   - Không được tự ý xác nhận phòng trống hay tự tính toán giá phòng cuối cùng khi "
            "chưa có thông tin kiểm tra từ hệ thống, hãy đề xuất để chủ homestay kiểm tra.\n"
            "4. Khi khách muốn chốt đặt phòng và đã cung cấp đủ thông tin "
            "(hoặc đồng ý giữ phòng):\n"
            "   - Đặt intent là 'booking_confirmation'.\n"
            "   - Đặt needs_human là true để hệ thống chuyển tiếp cho chủ nhà xác nhận.\n"
            "5. Phân loại Intent chính xác:\n"
            "   - 'faq': Câu hỏi chung về giờ check-in, địa chỉ, tiện ích...\n"
            "   - 'booking_inquiry': Khách hỏi giá, phòng trống, hỏi thông tin đặt phòng.\n"
            "   - 'booking_confirmation': Khách đồng ý đặt phòng, muốn giữ phòng, cung cấp SĐT để "
            "xác nhận đặt phòng.\n"
            "   - 'human_request': Khách yêu cầu gặp nhân viên hoặc chủ nhà trực tiếp.\n"
            "   - 'unknown': Không rõ ý định.\n"
            "6. Nếu khách yêu cầu gặp người thật hoặc hỏi câu hỏi quá phức tạp, "
            "đặt 'needs_human' = true và 'escalation_reason' = 'customer_requested_human'.\n"
            "7. Nếu bạn không chắc chắn về ý định của khách hoặc thông tin không rõ ràng, "
            "đặt 'needs_human' = true và 'escalation_reason' = 'low_ai_confidence' "
            "và tự hạ confidence xuống dưới 0.65."
        )

        messages = [{"role": "system", "content": system_prompt}]

        for h in history:
            role = "user" if h.role == MessageRole.CUSTOMER else "assistant"
            messages.append({"role": role, "content": h.text})

        messages.append({"role": "user", "content": message.text})

        try:
            response = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=messages,  # type: ignore
                response_format=OpenAIResponseSchema,
                timeout=self._timeout_seconds,
            )
        except OpenAIError as error:
            logger.error("OpenAI API call failed: %s", error, exc_info=True)
            raise AIProviderError(f"OpenAI API request failed: {error}") from error

        parsed = response.choices[0].message.parsed
        if not parsed:
            raise AIProviderError("OpenAI returned empty parsed response")

        # Sanitize and parse entities
        check_in = self._parse_date(parsed.entities.check_in)
        check_out = self._parse_date(parsed.entities.check_out)
        guest_count = parsed.entities.guest_count

        if guest_count is not None and guest_count < 1:
            guest_count = None

        if check_in and check_out and check_out <= check_in:
            check_out = None

        entities = ExtractedEntities(
            check_in=check_in,
            check_out=check_out,
            guest_count=guest_count,
            phone=parsed.entities.phone,
            room_name=parsed.entities.room_name,
        )

        return AIDecision(
            intent=parsed.intent,
            draft_reply=parsed.draft_reply,
            confidence=parsed.confidence,
            needs_human=parsed.needs_human,
            entities=entities,
            escalation_reason=parsed.escalation_reason,
        )
