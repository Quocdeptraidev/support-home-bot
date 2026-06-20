import hashlib
import hmac
import json
import uuid

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis.asyncio import Redis

from app.api.dependencies import _conversation_repository, _escalation_notifier
from app.core.config import Settings, get_settings
from app.domain.messaging import MessageRole
from app.main import app


def facebook_signature(raw_body: bytes, app_secret: str) -> str:
    digest = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


@pytest.fixture(autouse=True)
async def clear_states() -> None:
    # Clear mock repo state
    _conversation_repository._store.clear()
    _escalation_notifier.notices.clear()

    # Clear Redis database for test isolation
    redis_client = Redis.from_url(Settings().redis_url)
    try:
        await redis_client.flushdb()
    finally:
        await redis_client.aclose()


@respx.mock
async def test_facebook_webhook_post_happy_path(respx_mock: respx.MockRouter) -> None:
    app_secret = "my-app-secret"
    verify_token = "verify-me"
    page_access_token = "token-123"
    api_version = "v21.0"

    app.dependency_overrides[get_settings] = lambda: Settings(
        fb_app_secret=SecretStr(app_secret),
        fb_verify_token=SecretStr(verify_token),
        fb_page_access_token=SecretStr(page_access_token),
        fb_api_version=api_version,
        app_env="test",
    )

    try:
        meta_url = f"https://graph.facebook.com/{api_version}/me/messages"
        meta_route = respx_mock.post(meta_url).mock(
            return_value=httpx.Response(200, json={"message_id": "meta-msg-id"})
        )

        mid = f"msg-{uuid.uuid4()}"
        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "user-456"},
                            "timestamp": 1718438400000,
                            "message": {
                                "mid": mid,
                                "text": "Giá phòng bên mình thế nào ạ?",
                            },
                        }
                    ]
                }
            ],
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig = facebook_signature(raw_body, app_secret)

        client = TestClient(app)
        response = client.post(
            "/api/v1/webhooks/facebook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
        )

        assert response.status_code == 200
        assert response.text == "EVENT_RECEIVED"

        assert meta_route.called
        last_request = meta_route.calls.last.request
        assert last_request.headers["Authorization"] == f"Bearer {page_access_token}"
        req_body = json.loads(last_request.read().decode())
        assert req_body["recipient"]["id"] == "user-456"
        assert "Giá phòng tuỳ loại từ 650.000đ" in req_body["message"]["text"]

        history = await _conversation_repository.get_recent("user-456", 10)
        assert len(history) == 2
        assert history[0].role == MessageRole.CUSTOMER
        assert history[0].text == "Giá phòng bên mình thế nào ạ?"
        assert history[1].role == MessageRole.BOT
        assert "Giá phòng tuỳ loại từ 650.000đ" in history[1].text

    finally:
        app.dependency_overrides.clear()


@respx.mock
async def test_facebook_webhook_post_duplicate_message_is_ignored(
    respx_mock: respx.MockRouter,
) -> None:
    app_secret = "my-app-secret"
    app.dependency_overrides[get_settings] = lambda: Settings(
        fb_app_secret=SecretStr(app_secret),
        fb_verify_token=SecretStr("verify-me"),
        fb_page_access_token=SecretStr("token-123"),
        fb_api_version="v21.0",
        app_env="test",
    )

    try:
        meta_url = "https://graph.facebook.com/v21.0/me/messages"
        meta_route = respx_mock.post(meta_url).mock(
            return_value=httpx.Response(200, json={"message_id": "meta-msg-id"})
        )

        event_id = f"evt-{uuid.uuid4()}"
        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "user-789"},
                            "timestamp": 1718438400000,
                            "message": {
                                "mid": event_id,
                                "text": "Mấy giờ check-in?",
                            },
                        }
                    ]
                }
            ],
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig = facebook_signature(raw_body, app_secret)

        client = TestClient(app)

        response1 = client.post(
            "/api/v1/webhooks/facebook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response1.status_code == 200
        assert meta_route.call_count == 1

        response2 = client.post(
            "/api/v1/webhooks/facebook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response2.status_code == 200
        assert meta_route.call_count == 1

    finally:
        app.dependency_overrides.clear()
