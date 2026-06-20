"""Telegram notification adapters."""

from app.infrastructure.notifications.fake_escalation_notifier import (
    FakeEscalationNotifier,
)
from app.infrastructure.notifications.telegram_escalation_notifier import (
    TelegramEscalationNotifier,
)

__all__ = ["FakeEscalationNotifier", "TelegramEscalationNotifier"]
