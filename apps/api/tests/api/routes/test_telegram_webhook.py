import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.main import app


@pytest.mark.asyncio
async def test_telegram_webhook_skips_without_callback_query() -> None:
    # Gửi payload thiếu callback_query -> Bỏ qua
    response = TestClient(app).post(
        "/api/v1/webhooks/telegram",
        json={
            "update_id": 12345
        }
    )
    assert response.status_code == 200
    assert response.json() == {"status": "skipped", "reason": "no_callback_query"}


@pytest.mark.asyncio
async def test_telegram_webhook_rejects_missing_message() -> None:
    # Gửi payload thiếu context message -> Trả về 400
    response = TestClient(app).post(
        "/api/v1/webhooks/telegram",
        json={
            "update_id": 12345,
            "callback_query": {
                "id": "query-123",
                "data": "confirm_booking:7020c293-6c2b-4dae-860c-33702675cbf0"
            }
        }
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Callback query must contain message context"


@pytest.mark.asyncio
async def test_telegram_webhook_success_flow() -> None:
    booking_id = uuid.uuid4()
    
    # Mock use_case
    mock_use_case = AsyncMock()
    mock_use_case.execute.return_value = True
    
    # Override dependency
    from app.api.dependencies import get_process_telegram_callback_use_case
    app.dependency_overrides[get_process_telegram_callback_use_case] = lambda: mock_use_case

    try:
        response = TestClient(app).post(
            "/api/v1/webhooks/telegram",
            json={
                "update_id": 12345,
                "callback_query": {
                    "id": "query-123",
                    "data": f"confirm_booking:{booking_id}",
                    "message": {
                        "message_id": 999,
                        "chat": {"id": -456},
                        "text": "Khách đặt phòng"
                    }
                }
            }
        )
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_use_case.execute.assert_called_once_with(
            callback_query_id="query-123",
            chat_id="-456",
            message_id="999",
            message_text="Khách đặt phòng",
            callback_data=f"confirm_booking:{booking_id}"
        )
    finally:
        app.dependency_overrides.clear()
