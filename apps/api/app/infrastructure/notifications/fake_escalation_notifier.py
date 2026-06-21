from app.domain.messaging import EscalationNotice
from app.domain.ports import EscalationNotifier


class FakeEscalationNotifier(EscalationNotifier):
    def __init__(self) -> None:
        self.notices: list[EscalationNotice] = []

    async def notify(self, notice: EscalationNotice) -> None:
        self.notices.append(notice)

    async def edit_message_text(self, *, chat_id: str, message_id: str, new_text: str) -> bool:
        return True

    async def answer_callback_query(self, *, callback_query_id: str, text: str) -> bool:
        return True
