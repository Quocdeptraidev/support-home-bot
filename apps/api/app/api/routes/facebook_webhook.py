import hmac
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.core.config import Settings, get_settings
from app.core.security import verify_facebook_signature
from app.infrastructure.messaging.facebook_event_parser import (
    InvalidFacebookWebhookPayload,
    parse_facebook_messages,
)

router = APIRouter(prefix="/api/v1/webhooks/facebook", tags=["facebook-webhook"])


@router.get("", response_class=PlainTextResponse)
def verify_facebook_webhook(
    mode: Annotated[str, Query(alias="hub.mode")],
    verify_token: Annotated[str, Query(alias="hub.verify_token")],
    challenge: Annotated[str, Query(alias="hub.challenge")],
    config: Annotated[Settings, Depends(get_settings)],
) -> str:
    expected_token = config.fb_verify_token.get_secret_value()
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Facebook integration is not configured",
        )

    token_matches = hmac.compare_digest(verify_token, expected_token)
    if mode != "subscribe" or not token_matches:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Facebook verify token",
        )

    return challenge


@router.post("", response_class=PlainTextResponse)
async def receive_facebook_webhook(
    request: Request,
    config: Annotated[Settings, Depends(get_settings)],
    signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> str:
    app_secret = config.fb_app_secret.get_secret_value()
    if not app_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Facebook integration is not configured",
        )

    raw_body = await request.body()
    if not verify_facebook_signature(raw_body, signature, app_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Facebook webhook signature",
        )

    try:
        payload = json.loads(raw_body)
        parse_facebook_messages(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, InvalidFacebookWebhookPayload) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Facebook webhook payload",
        ) from error

    return "EVENT_RECEIVED"
