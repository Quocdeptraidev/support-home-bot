import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.infrastructure.calendar.fake_calendar_adapter import FakeCalendarAdapter
from app.infrastructure.calendar.google_calendar_adapter import GoogleCalendarAdapter


@pytest.mark.asyncio
async def test_fake_calendar_adapter_create_event() -> None:
    adapter = FakeCalendarAdapter()
    start = datetime(2026, 6, 20, 14, 0, tzinfo=UTC)
    end = datetime(2026, 6, 20, 17, 0, tzinfo=UTC)

    event_id = await adapter.create_event(
        title="Test Event",
        start_time=start,
        end_time=end,
        description="Testing fake calendar description",
    )

    assert event_id is not None
    assert len(adapter.events) == 1
    assert adapter.events[0]["title"] == "Test Event"
    assert adapter.events[0]["start_time"] == start
    assert adapter.events[0]["end_time"] == end
    assert adapter.events[0]["description"] == "Testing fake calendar description"


@pytest.mark.asyncio
async def test_google_calendar_adapter_invalid_credentials() -> None:
    # Test initialization failure with invalid JSON credentials
    with pytest.raises(ValueError):
        GoogleCalendarAdapter(
            calendar_id="test-calendar-id",
            service_account_info=SecretStr("invalid-json-credentials"),
        )


@pytest.mark.asyncio
async def test_google_calendar_adapter_success_api_call() -> None:
    # Mock Google service account JSON
    mock_credentials_json = json.dumps({
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "123456",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC3\n-----END PRIVATE KEY-----\n",
        "client_email": "test-service-account@test-project.iam.gserviceaccount.com",
        "client_id": "111222333",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    })

    start = datetime(2026, 6, 20, 14, 0, tzinfo=UTC)
    end = datetime(2026, 6, 20, 17, 0, tzinfo=UTC)

    # Patch google service_account.Credentials.from_service_account_info
    # and credentials.refresh to avoid real Google authentication
    with patch("google.oauth2.service_account.Credentials.from_service_account_info") as mock_from_info:
        mock_creds = MagicMock()
        mock_creds.token = "mock-google-access-token"
        mock_from_info.return_value = mock_creds

        adapter = GoogleCalendarAdapter(
            calendar_id="test-calendar-id",
            service_account_info=SecretStr(mock_credentials_json),
        )

        # Mock httpx.AsyncClient post response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "event-id-123456789"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            event_id = await adapter.create_event(
                title="Google Test Event",
                start_time=start,
                end_time=end,
                description="Testing Google Calendar API Integration",
            )

            assert event_id == "event-id-123456789"
            assert mock_post.called
            call_url = mock_post.call_args[0][0]
            assert "test-calendar-id" in call_url
            
            call_json = mock_post.call_args[1]["json"]
            assert call_json["summary"] == "Google Test Event"
            assert call_json["start"]["dateTime"] == start.isoformat()
