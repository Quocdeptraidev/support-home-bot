import logging
import uuid
from datetime import datetime

from app.domain.ports import CalendarGateway

logger = logging.getLogger(__name__)


class FakeCalendarAdapter(CalendarGateway):
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def create_event(
        self,
        *,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str,
    ) -> str | None:
        event_id = str(uuid.uuid4())
        event = {
            "id": event_id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "description": description,
        }
        self.events.append(event)
        logger.info(
            "FakeCalendarAdapter: Created event '%s' from %s to %s. Desc: %s. Event ID: %s",
            title,
            start_time,
            end_time,
            description,
            event_id,
        )
        return event_id
