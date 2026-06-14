from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.main import app


def test_facebook_webhook_verification_returns_challenge() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        fb_verify_token=SecretStr("verify-me")
    )

    try:
        response = TestClient(app).get(
            "/api/v1/webhooks/facebook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "challenge-value",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text == "challenge-value"


def test_facebook_webhook_verification_rejects_invalid_token() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        fb_verify_token=SecretStr("verify-me")
    )

    try:
        response = TestClient(app).get(
            "/api/v1/webhooks/facebook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "challenge-value",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
