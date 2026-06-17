from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, ValidationError

from app.domain.messaging import IncomingMessage


class InvalidFacebookWebhookPayload(ValueError):
    pass


class FacebookSender(BaseModel):
    id: str

    model_config = ConfigDict(extra="ignore")


class FacebookMessage(BaseModel):
    mid: str
    text: str | None = None
    is_echo: bool = False

    model_config = ConfigDict(extra="ignore")


class FacebookMessagingEvent(BaseModel):
    sender: FacebookSender
    timestamp: int
    message: FacebookMessage | None = None

    model_config = ConfigDict(extra="ignore")


class FacebookEntry(BaseModel):
    messaging: list[FacebookMessagingEvent] = []

    model_config = ConfigDict(extra="ignore")


class FacebookWebhookPayload(BaseModel):
    object: str
    entry: list[FacebookEntry]

    model_config = ConfigDict(extra="ignore")


def parse_facebook_messages(payload: object) -> list[IncomingMessage]:
    try:
        webhook = FacebookWebhookPayload.model_validate(payload)
    except ValidationError as error:
        raise InvalidFacebookWebhookPayload("Invalid Facebook webhook payload") from error

    if webhook.object != "page":
        return []

    messages: list[IncomingMessage] = []
    for entry in webhook.entry:
        for event in entry.messaging:
            message = event.message
            if message is None or message.is_echo or not message.text:
                continue

            messages.append(
                IncomingMessage(
                    event_id=message.mid,
                    message_id=message.mid,
                    sender_id=event.sender.id,
                    text=message.text,
                    received_at=datetime.fromtimestamp(event.timestamp / 1000, tz=UTC),
                )
            )

    return messages
