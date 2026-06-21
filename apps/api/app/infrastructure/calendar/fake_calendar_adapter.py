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
        color_id: str | None = None,
    ) -> str | None:
        event_id = str(uuid.uuid4())
        event = {
            "id": event_id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "description": description,
            "color_id": color_id,
        }
        self.events.append(event)
        logger.info(
            "FakeCalendarAdapter: Created event '%s' with color '%s' from %s to %s. Desc: %s. Event ID: %s",
            title,
            color_id,
            start_time,
            end_time,
            description,
            event_id,
        )
        return event_id

    async def update_event_title(self, *, event_id: str, new_title: str, color_id: str | None = None) -> bool:
        for event in self.events:
            if event["id"] == event_id:
                event["title"] = new_title
                event["color_id"] = color_id
                logger.info("FakeCalendarAdapter: Updated event '%s' title to '%s' and color to '%s'", event_id, new_title, color_id)
                return True
        logger.warning("FakeCalendarAdapter: Event '%s' not found for update", event_id)
        return False
