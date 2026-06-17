from app.domain.messaging import EscalationNotice
from app.domain.ports import EscalationNotifier


class FakeEscalationNotifier(EscalationNotifier):
    def __init__(self) -> None:
        self.notices: list[EscalationNotice] = []

    async def notify(self, notice: EscalationNotice) -> None:
        self.notices.append(notice)
