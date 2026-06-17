from datetime import UTC, datetime

import pytest

from app.infrastructure.messaging.facebook_event_parser import (
    InvalidFacebookWebhookPayload,
    parse_facebook_messages,
)


def test_parse_facebook_messages_maps_text_message() -> None:
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "customer-123"},
                        "timestamp": 1718438400000,
                        "message": {
                            "mid": "message-123",
                            "text": "Homestay mấy giờ nhận phòng?",
                        },
                    }
                ]
            }
        ],
    }

    messages = parse_facebook_messages(payload)

    assert len(messages) == 1
    assert messages[0].event_id == "message-123"
    assert messages[0].message_id == "message-123"
    assert messages[0].sender_id == "customer-123"
    assert messages[0].text == "Homestay mấy giờ nhận phòng?"
    assert messages[0].received_at == datetime(2024, 6, 15, 8, 0, tzinfo=UTC)


def test_parse_facebook_messages_ignores_echo_and_unsupported_events() -> None:
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "page-123"},
                        "timestamp": 1718438400000,
                        "message": {
                            "mid": "echo-123",
                            "text": "Tin nhắn từ Page",
                            "is_echo": True,
                        },
                    },
                    {
                        "sender": {"id": "customer-123"},
                        "timestamp": 1718438400000,
                        "delivery": {"mids": ["message-123"]},
                    },
                    {
                        "sender": {"id": "customer-123"},
                        "timestamp": 1718438400000,
                        "message": {
                            "mid": "attachment-123",
                            "attachments": [{"type": "image"}],
                        },
                    },
                ]
            }
        ],
    }

    assert parse_facebook_messages(payload) == []


def test_parse_facebook_messages_ignores_non_page_payload() -> None:
    payload = {"object": "instagram", "entry": []}

    assert parse_facebook_messages(payload) == []


def test_parse_facebook_messages_rejects_malformed_payload() -> None:
    with pytest.raises(
        InvalidFacebookWebhookPayload,
        match="Invalid Facebook webhook payload",
    ):
        parse_facebook_messages({"object": "page"})
