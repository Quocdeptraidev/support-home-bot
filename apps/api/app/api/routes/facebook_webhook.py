import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.core.config import Settings, get_settings

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
