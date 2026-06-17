"""Telegram notification adapters."""

from app.infrastructure.notifications.fake_escalation_notifier import (
    FakeEscalationNotifier,
)

__all__ = ["FakeEscalationNotifier"]
