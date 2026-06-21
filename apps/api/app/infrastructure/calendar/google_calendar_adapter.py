import json
import logging
from datetime import datetime
from pydantic import SecretStr

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from app.domain.ports import CalendarGateway

logger = logging.getLogger(__name__)


class GoogleCalendarAdapter(CalendarGateway):
    def __init__(
        self,
        *,
        calendar_id: str,
        service_account_info: SecretStr,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._calendar_id = calendar_id
        self._service_account_info = service_account_info
        self._timeout_seconds = timeout_seconds

        # Parse credentials info
        try:
            info_dict = json.loads(self._service_account_info.get_secret_value())
            self._credentials = service_account.Credentials.from_service_account_info(
                info_dict,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
        except Exception as e:
            logger.error("Failed to parse Google Service Account Credentials: %s", e)
            raise ValueError(f"Invalid Google Service Account Credentials: {e}") from e

    async def _get_access_token(self) -> str:
        """
        Refresh credentials in a thread-safe way and return access token.
        """
        # Google Auth refresh is synchronous, we run it to ensure token is fresh
        try:
            self._credentials.refresh(Request())
            token = self._credentials.token
            if not token:
                raise ValueError("Token is empty after refresh")
            return token
        except Exception as e:
            logger.error("Failed to refresh Google access token: %s", e)
            raise

    async def create_event(
        self,
        *,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str,
        color_id: str | None = None,
    ) -> str | None:
        try:
            access_token = await self._get_access_token()
        except Exception as e:
            logger.error("Failed to authenticate with Google: %s", e)
            return None

        url = f"https://www.googleapis.com/calendar/v3/calendars/{self._calendar_id}/events"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Google API requires datetime in ISO 8601 format (e.g. YYYY-MM-DDTHH:MM:SSZ)
        payload = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
            },
            "end": {
                "dateTime": end_time.isoformat(),
            },
        }
        if color_id:
            payload["colorId"] = color_id

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    event_data = response.json()
                    event_id = event_data.get("id")
                    logger.info("Successfully created Google Calendar Event with color %s. ID: %s", color_id, event_id)
                    return event_id
                else:
                    logger.error(
                        "Google Calendar API returned error status %d: %s",
                        response.status_code,
                        response.text,
                    )
        except Exception as e:
            logger.error("Failed to call Google Calendar API: %s", e, exc_info=True)

        return None

    async def update_event_title(self, *, event_id: str, new_title: str, color_id: str | None = None) -> bool:
        try:
            access_token = await self._get_access_token()
        except Exception as e:
            logger.error("Failed to authenticate with Google to update event: %s", e)
            return False

        url = f"https://www.googleapis.com/calendar/v3/calendars/{self._calendar_id}/events/{event_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "summary": new_title,
        }
        if color_id:
            payload["colorId"] = color_id

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.patch(url, headers=headers, json=payload)
                if response.status_code == 200:
                    logger.info("Successfully updated Google Calendar Event title and color %s. ID: %s", color_id, event_id)
                    return True
                else:
                    logger.error(
                        "Google Calendar API returned error status %d on update: %s",
                        response.status_code,
                        response.text,
                    )
        except Exception as e:
            logger.error("Failed to update Google Calendar API: %s", e, exc_info=True)

        return False
