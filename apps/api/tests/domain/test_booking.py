import uuid
from datetime import datetime, UTC

import pytest

from app.domain.booking import (
    Booking,
    BookingStatus,
    Room,
    is_overnight_booking,
    calculate_booking_price,
    calculate_duration_display,
    check_overlap,
)


def test_is_overnight_booking() -> None:
    # Overnight: different dates
    check_in = datetime(2026, 6, 20, 14, 0, tzinfo=UTC)
    check_out = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    assert is_overnight_booking(check_in, check_out) is True

    # Overnight: same date but >= 12 hours
    check_in_same = datetime(2026, 6, 20, 8, 0, tzinfo=UTC)
    check_out_same = datetime(2026, 6, 20, 20, 0, tzinfo=UTC)
    assert is_overnight_booking(check_in_same, check_out_same) is True

    # Hourly: same date and < 12 hours
    check_in_hourly = datetime(2026, 6, 20, 19, 0, tzinfo=UTC)
    check_out_hourly = datetime(2026, 6, 20, 22, 0, tzinfo=UTC)
    assert is_overnight_booking(check_in_hourly, check_out_hourly) is False


def test_calculate_booking_price() -> None:
    room = Room(
        id=uuid.uuid4(),
        name="Home 1",
        price_per_night=600000,
        price_per_hour=100000,
        capacity=2,
    )

    # Overnight (1 night)
    check_in = datetime(2026, 6, 20, 14, 0, tzinfo=UTC)
    check_out = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    assert calculate_booking_price(room, check_in, check_out) == 600000

    # Hourly (3 hours)
    check_in_hourly = datetime(2026, 6, 20, 19, 0, tzinfo=UTC)
    check_out_hourly = datetime(2026, 6, 20, 22, 0, tzinfo=UTC)
    assert calculate_booking_price(room, check_in_hourly, check_out_hourly) == 300000

    # Hourly (minimum 2 hours enforced)
    check_in_short = datetime(2026, 6, 20, 19, 0, tzinfo=UTC)
    check_out_short = datetime(2026, 6, 20, 20, 0, tzinfo=UTC)
    assert calculate_booking_price(room, check_in_short, check_out_short) == 200000


def test_calculate_duration_display() -> None:
    # Overnight
    check_in = datetime(2026, 6, 20, 14, 0, tzinfo=UTC)
    check_out = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    assert calculate_duration_display(check_in, check_out) == "1 đêm"

    # Hourly
    check_in_hourly = datetime(2026, 6, 20, 19, 0, tzinfo=UTC)
    check_out_hourly = datetime(2026, 6, 20, 22, 0, tzinfo=UTC)
    assert calculate_duration_display(check_in_hourly, check_out_hourly) == "3 tiếng"


def test_check_overlap() -> None:
    # Overlapping
    assert check_overlap(
        datetime(2026, 6, 20, 14, 0), datetime(2026, 6, 20, 17, 0),
        datetime(2026, 6, 20, 16, 0), datetime(2026, 6, 20, 18, 0)
    )

    # Non-overlapping
    assert not check_overlap(
        datetime(2026, 6, 20, 14, 0), datetime(2026, 6, 20, 16, 0),
        datetime(2026, 6, 20, 16, 0), datetime(2026, 6, 20, 18, 0)
    )


def test_booking_validation() -> None:
    cid = uuid.uuid4()
    rid = uuid.uuid4()
    bid = uuid.uuid4()

    # Valid booking
    booking = Booking(
        id=bid,
        conversation_id=cid,
        room_id=rid,
        check_in=datetime(2026, 6, 20, 14, 0, tzinfo=UTC),
        check_out=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
        guest_count=2,
        phone="0909123456",
        total_price=600000,
        status=BookingStatus.PENDING,
    )
    assert booking.guest_count == 2
    assert booking.status == BookingStatus.PENDING

    # Invalid date range
    with pytest.raises(ValueError, match="check_out must be after check_in"):
        Booking(
            id=bid,
            conversation_id=cid,
            room_id=rid,
            check_in=datetime(2026, 6, 20, 14, 0, tzinfo=UTC),
            check_out=datetime(2026, 6, 20, 13, 0, tzinfo=UTC),
            guest_count=2,
            phone="0909123456",
            total_price=600000,
        )

    # Invalid guest count
    with pytest.raises(ValueError, match="guest_count must be greater than zero"):
        Booking(
            id=bid,
            conversation_id=cid,
            room_id=rid,
            check_in=datetime(2026, 6, 20, 14, 0, tzinfo=UTC),
            check_out=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            guest_count=0,
            phone="0909123456",
            total_price=600000,
        )
