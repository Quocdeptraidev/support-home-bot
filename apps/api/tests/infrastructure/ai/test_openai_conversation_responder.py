from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import OpenAIError
from pydantic import SecretStr

from app.application.errors import AIProviderError
from app.domain.messaging import (
    ConversationMessage,
    IncomingMessage,
    Intent,
    MessageRole,
)
from app.infrastructure.ai.openai_conversation_responder import (
    OpenAIConversationResponder,
    OpenAIEntities,
    OpenAIResponseSchema,
)


@pytest.fixture
def responder() -> OpenAIConversationResponder:
    return OpenAIConversationResponder(
        api_key=SecretStr("mock-key-123"),
        model="gpt-4o-mini",
        timeout_seconds=30.0,
    )


@pytest.mark.asyncio
async def test_openai_responder_analyze_success(responder: OpenAIConversationResponder) -> None:
    message = IncomingMessage(
        event_id="evt-1",
        message_id="mid-1",
        sender_id="user-123",
        text="Tôi muốn đặt phòng 2 người ngày mai",
        received_at=datetime.now(UTC),
    )
    history = [
        ConversationMessage(role=MessageRole.CUSTOMER, text="Chào bạn"),
        ConversationMessage(role=MessageRole.BOT, text="Dạ chào anh/chị ạ!"),
    ]

    mock_parsed_response = OpenAIResponseSchema(
        intent=Intent.BOOKING_INQUIRY,
        draft_reply="Dạ mình muốn check-in ngày nào ạ?",
        confidence=0.92,
        needs_human=False,
        entities=OpenAIEntities(
            check_in="2026-06-19",
            guest_count=2,
        ),
    )

    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_response

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    # Mock AsyncOpenAI beta.chat.completions.parse method
    with patch.object(
        responder._client.beta.chat.completions,
        "parse",
        new_callable=AsyncMock,
        return_value=mock_completion,
    ) as mock_parse:
        decision = await responder.analyze(message, history)

        assert mock_parse.called
        call_args = mock_parse.call_args[1]
        assert call_args["model"] == "gpt-4o-mini"
        assert len(call_args["messages"]) == 4  # system prompt + 2 history + current message

        assert decision.intent == Intent.BOOKING_INQUIRY
        assert decision.draft_reply == "Dạ mình muốn check-in ngày nào ạ?"
        assert decision.confidence == 0.92
        assert decision.needs_human is False
        assert decision.entities.guest_count == 2
        assert decision.entities.check_in is not None
        assert decision.entities.check_in.strftime("%Y-%m-%d") == "2026-06-19"


@pytest.mark.asyncio
async def test_openai_responder_api_error(responder: OpenAIConversationResponder) -> None:
    message = IncomingMessage(
        event_id="evt-1",
        message_id="mid-1",
        sender_id="user-123",
        text="Hello",
        received_at=datetime.now(UTC),
    )

    with patch.object(
        responder._client.beta.chat.completions,
        "parse",
        new_callable=AsyncMock,
        side_effect=OpenAIError("Connection timeout"),
    ):
        with pytest.raises(AIProviderError) as exc_info:
            await responder.analyze(message, [])

        assert "OpenAI API request failed" in str(exc_info.value)
