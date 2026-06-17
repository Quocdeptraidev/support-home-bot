import hashlib
import hmac

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.main import app


def facebook_signature(raw_body: bytes, app_secret: str) -> str:
    digest = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


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


def test_facebook_webhook_event_accepts_valid_signature() -> None:
    app_secret = "app-secret"
    raw_body = b'{"object":"page","entry":[]}'
    app.dependency_overrides[get_settings] = lambda: Settings(fb_app_secret=SecretStr(app_secret))

    try:
        response = TestClient(app).post(
            "/api/v1/webhooks/facebook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": facebook_signature(raw_body, app_secret),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text == "EVENT_RECEIVED"


def test_facebook_webhook_event_rejects_invalid_signature() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(fb_app_secret=SecretStr("app-secret"))

    try:
        response = TestClient(app).post(
            "/api/v1/webhooks/facebook",
            content=b'{"object":"page","entry":[]}',
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_facebook_webhook_event_requires_configured_app_secret() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(fb_app_secret=SecretStr(""))

    try:
        response = TestClient(app).post(
            "/api/v1/webhooks/facebook",
            content=b'{"object":"page","entry":[]}',
            headers={"Content-Type": "application/json"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_facebook_webhook_event_rejects_invalid_json() -> None:
    app_secret = "app-secret"
    raw_body = b'{"object":"page"'
    app.dependency_overrides[get_settings] = lambda: Settings(fb_app_secret=SecretStr(app_secret))

    try:
        response = TestClient(app).post(
            "/api/v1/webhooks/facebook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": facebook_signature(raw_body, app_secret),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Facebook webhook payload"}


def test_facebook_webhook_event_rejects_invalid_payload_schema() -> None:
    app_secret = "app-secret"
    raw_body = b'{"object":"page"}'
    app.dependency_overrides[get_settings] = lambda: Settings(fb_app_secret=SecretStr(app_secret))

    try:
        response = TestClient(app).post(
            "/api/v1/webhooks/facebook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": facebook_signature(raw_body, app_secret),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Facebook webhook payload"}


def test_facebook_webhook_event_acknowledges_echo_event() -> None:
    app_secret = "app-secret"
    raw_body = (
        b'{"object":"page","entry":[{"messaging":[{"sender":{"id":"page-123"},'
        b'"timestamp":1718438400000,"message":{"mid":"echo-123","text":"Echo",'
        b'"is_echo":true}}]}]}'
    )
    app.dependency_overrides[get_settings] = lambda: Settings(fb_app_secret=SecretStr(app_secret))

    try:
        response = TestClient(app).post(
            "/api/v1/webhooks/facebook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": facebook_signature(raw_body, app_secret),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text == "EVENT_RECEIVED"
