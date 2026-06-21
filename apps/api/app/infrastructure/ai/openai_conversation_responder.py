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
            "Check-in date and time in YYYY-MM-DD HH:MM format. If time is not specified by the user, default to 14:00. "
            "Example: '2026-05-16 19:00'."
        ),
    )
    check_out: str | None = Field(
        default=None,
        description=(
            "Check-out date and time in YYYY-MM-DD HH:MM format. If time is not specified by the user, default to 12:00 "
            "on the next day."
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
        system_prompt_template: str = "",
        timezone_name: str = "Asia/Ho_Chi_Minh",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._system_prompt_template = system_prompt_template
        self._timezone_name = timezone_name

        key_val = self._api_key.get_secret_value()
        if not key_val:
            raise AIProviderError("OpenAI API key is not configured")

        self._client = AsyncOpenAI(api_key=key_val)

    def _parse_datetime(self, datetime_str: str | None) -> datetime | None:
        if not datetime_str:
            return None
        try:
            parsed = dateparser.parse(
                datetime_str,
                settings={
                    "TIMEZONE": self._timezone_name,
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "PREFER_DATES_FROM": "future",
                }
            )
            if parsed:
                from datetime import UTC
                return parsed.astimezone(UTC)
        except Exception:
            pass
        return None

    async def analyze(
        self,
        message: IncomingMessage,
        history: Sequence[ConversationMessage],
    ) -> AIDecision:
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Nạp động thời gian hệ thống vào template prompt bằng .replace() tránh xung đột cú pháp ngoặc nhọn
        system_prompt = self._system_prompt_template.replace(
            "{current_time_str}", current_time_str
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
        check_in = self._parse_datetime(parsed.entities.check_in)
        check_out = self._parse_datetime(parsed.entities.check_out)
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
