import uuid
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock

from app.application.use_cases.process_telegram_callback import ProcessTelegramCallback
from app.domain.booking import Booking, BookingStatus, Room


from app.infrastructure.persistence.in_memory_booking_repository import InMemoryBookingRepository
from app.infrastructure.persistence.in_memory_conversation_repository import InMemoryConversationRepository

# Sử dụng lại các Fake gateways có sẵn từ test_process_incoming_message
from tests.application.test_process_incoming_message import (
    FakeMessageGateway,
    FakeEscalationNotifier,
    FakeRoomRepository,
    FakeCalendarGateway,
)


@pytest.mark.asyncio
async def test_process_telegram_callback_confirm_booking_success() -> None:
    booking_repository = InMemoryBookingRepository()
    conversation_repository = InMemoryConversationRepository()
    message_gateway = FakeMessageGateway()
    escalation_notifier = FakeEscalationNotifier()
    calendar_gateway = FakeCalendarGateway()
    
    room_id = uuid.uuid4()
    room = Room(id=room_id, name="Home 1", price_per_night=600000, price_per_hour=100000, capacity=2)
    room_repository = FakeRoomRepository([room])

    # Tạo mock methods cho FakeEscalationNotifier & FakeCalendarGateway
    escalation_notifier.edit_message_text = AsyncMock(return_value=True)
    escalation_notifier.answer_callback_query = AsyncMock(return_value=True)
    calendar_gateway.update_event_title = AsyncMock(return_value=True)

    conversation_id = uuid.uuid4()
    booking_id = uuid.uuid4()
    
    booking = Booking(
        id=booking_id,
        conversation_id=conversation_id,
        room_id=room_id,
        check_in=datetime(2026, 6, 20, 14, 0, tzinfo=UTC),
        check_out=datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
        guest_count=2,
        phone="0909123456",
        total_price=1200000,
        status=BookingStatus.PENDING,
        google_calendar_event_id="google-event-123",
    )
    await booking_repository.create(booking)
    
    # Giả lập conversation để lấy PSID
    conversation_repository._conv_to_user[conversation_id] = "facebook-user-1"

    use_case = ProcessTelegramCallback(
        booking_repository=booking_repository,
        room_repository=room_repository,
        conversation_repository=conversation_repository,
        calendar_gateway=calendar_gateway,
        message_gateway=message_gateway,
        escalation_notifier=escalation_notifier,
    )

    result = await use_case.execute(
        callback_query_id="query-id-1",
        chat_id="chat-1",
        message_id="msg-1",
        message_text="⚠️ CẦN CAN THIỆP (ESCALATION)\nNội dung gốc",
        callback_data=f"confirm_booking:{booking_id}",
    )

    assert result is True
    # Kiểm tra database booking đã CONFIRMED
    updated = await booking_repository.get_by_id(booking_id)
    assert updated.status == BookingStatus.CONFIRMED

    # Kiểm tra Google Calendar được gọi update title
    calendar_gateway.update_event_title.assert_called_once_with(
        event_id="google-event-123",
        new_title="[ĐẶT PHÒNG CONFIRMED] Home 1 - SĐT: 0909123456",
        color_id="10",
    )

    # Kiểm tra Messenger phản hồi khách
    assert len(message_gateway.sent) == 1
    assert message_gateway.sent[0][0] == "facebook-user-1"
    assert "xác nhận thành công" in message_gateway.sent[0][1]

    # Kiểm tra Telegram message được edit
    escalation_notifier.edit_message_text.assert_called_once()
    edit_text = escalation_notifier.edit_message_text.call_args[1]["new_text"]
    assert "ĐÃ XỬ LÝ - <b>ĐÃ XÁC NHẬN ✅</b>" in edit_text

    # Kiểm tra Telegram answer callback query
    escalation_notifier.answer_callback_query.assert_called_once_with(
        callback_query_id="query-id-1",
        text="Đã xác nhận đặt phòng thành công!",
    )


@pytest.mark.asyncio
async def test_process_telegram_callback_cancel_booking_success() -> None:
    booking_repository = InMemoryBookingRepository()
    conversation_repository = InMemoryConversationRepository()
    message_gateway = FakeMessageGateway()
    escalation_notifier = FakeEscalationNotifier()
    calendar_gateway = FakeCalendarGateway()
    
    room_id = uuid.uuid4()
    room = Room(id=room_id, name="Home 1", price_per_night=600000, price_per_hour=100000, capacity=2)
    room_repository = FakeRoomRepository([room])

    # Tạo mock methods
    escalation_notifier.edit_message_text = AsyncMock(return_value=True)
    escalation_notifier.answer_callback_query = AsyncMock(return_value=True)
    calendar_gateway.update_event_title = AsyncMock(return_value=True)

    conversation_id = uuid.uuid4()
    booking_id = uuid.uuid4()
    
    booking = Booking(
        id=booking_id,
        conversation_id=conversation_id,
        room_id=room_id,
        check_in=datetime(2026, 6, 20, 14, 0, tzinfo=UTC),
        check_out=datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
        guest_count=2,
        phone="0909123456",
        total_price=1200000,
        status=BookingStatus.PENDING,
        google_calendar_event_id="google-event-123",
    )
    await booking_repository.create(booking)
    conversation_repository._conv_to_user[conversation_id] = "facebook-user-1"

    use_case = ProcessTelegramCallback(
        booking_repository=booking_repository,
        room_repository=room_repository,
        conversation_repository=conversation_repository,
        calendar_gateway=calendar_gateway,
        message_gateway=message_gateway,
        escalation_notifier=escalation_notifier,
    )

    result = await use_case.execute(
        callback_query_id="query-id-1",
        chat_id="chat-1",
        message_id="msg-1",
        message_text="⚠️ CẦN CAN THIỆP (ESCALATION)\nNội dung gốc",
        callback_data=f"cancel_booking:{booking_id}",
    )

    assert result is True
    updated = await booking_repository.get_by_id(booking_id)
    assert updated.status == BookingStatus.CANCELED

    calendar_gateway.update_event_title.assert_called_once_with(
        event_id="google-event-123",
        new_title="[ĐẶT PHÒNG CANCELED] Home 1 - SĐT: 0909123456",
        color_id="8",
    )

    assert "đã bị hủy" in message_gateway.sent[0][1]

    escalation_notifier.edit_message_text.assert_called_once()
    edit_text = escalation_notifier.edit_message_text.call_args[1]["new_text"]
    assert "ĐÃ XỬ LÝ - <b>ĐÃ HỦY ❌</b>" in edit_text


@pytest.mark.asyncio
async def test_process_telegram_callback_rejects_already_processed() -> None:
    booking_repository = InMemoryBookingRepository()
    conversation_repository = InMemoryConversationRepository()
    message_gateway = FakeMessageGateway()
    escalation_notifier = FakeEscalationNotifier()
    calendar_gateway = FakeCalendarGateway()
    
    room_id = uuid.uuid4()
    room = Room(id=room_id, name="Home 1", price_per_night=600000, price_per_hour=100000, capacity=2)
    room_repository = FakeRoomRepository([room])

    # Tạo mock methods
    escalation_notifier.answer_callback_query = AsyncMock(return_value=True)

    conversation_id = uuid.uuid4()
    booking_id = uuid.uuid4()
    
    booking = Booking(
        id=booking_id,
        conversation_id=conversation_id,
        room_id=room_id,
        check_in=datetime(2026, 6, 20, 14, 0, tzinfo=UTC),
        check_out=datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
        guest_count=2,
        phone="0909123456",
        total_price=1200000,
        status=BookingStatus.CONFIRMED,
    )
    await booking_repository.create(booking)

    use_case = ProcessTelegramCallback(
        booking_repository=booking_repository,
        room_repository=room_repository,
        conversation_repository=conversation_repository,
        calendar_gateway=calendar_gateway,
        message_gateway=message_gateway,
        escalation_notifier=escalation_notifier,
    )

    result = await use_case.execute(
        callback_query_id="query-id-1",
        chat_id="chat-1",
        message_id="msg-1",
        message_text="Tin nhắn gốc",
        callback_data=f"confirm_booking:{booking_id}",
    )

    assert result is False
    escalation_notifier.answer_callback_query.assert_called_once()
    assert "trước đó" in escalation_notifier.answer_callback_query.call_args[1]["text"]
