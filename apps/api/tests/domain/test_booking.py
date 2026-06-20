import uuid
from datetime import date

import pytest

from app.domain.booking import (
    Booking,
    BookingStatus,
    calculate_nights,
    calculate_total_price,
    check_overlap,
)


def test_calculate_nights_happy_path() -> None:
    check_in = date(2026, 6, 20)
    check_out = date(2026, 6, 22)
    assert calculate_nights(check_in, check_out) == 2


def test_calculate_nights_invalid_range() -> None:
    check_in = date(2026, 6, 22)
    check_out = date(2026, 6, 20)
    with pytest.raises(ValueError, match="check_out must be after check_in"):
        calculate_nights(check_in, check_out)


def test_calculate_total_price() -> None:
    assert calculate_total_price(650000, 2) == 1300000


def test_calculate_total_price_invalid() -> None:
    with pytest.raises(ValueError):
        calculate_total_price(-1, 2)
    with pytest.raises(ValueError):
        calculate_total_price(100, -2)


def test_check_overlap() -> None:
    # Overlapping intervals
    # Case 1: b1: [20, 22), b2: [21, 23)
    assert check_overlap(date(2026, 6, 20), date(2026, 6, 22), date(2026, 6, 21), date(2026, 6, 23))

    # Case 2: b1: [21, 23), b2: [20, 22)
    assert check_overlap(date(2026, 6, 21), date(2026, 6, 23), date(2026, 6, 20), date(2026, 6, 22))

    # Case 3: b1: [20, 25), b2: [21, 22)
    assert check_overlap(date(2026, 6, 20), date(2026, 6, 25), date(2026, 6, 21), date(2026, 6, 22))

    # Non-overlapping intervals
    # Case 4: b1: [20, 22), b2: [22, 24)
    assert not check_overlap(
        date(2026, 6, 20), date(2026, 6, 22), date(2026, 6, 22), date(2026, 6, 24)
    )

    # Case 5: b1: [22, 24), b2: [20, 22)
    assert not check_overlap(
        date(2026, 6, 22), date(2026, 6, 24), date(2026, 6, 20), date(2026, 6, 22)
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
        check_in=date(2026, 6, 20),
        check_out=date(2026, 6, 22),
        guest_count=2,
        phone="0909123456",
        total_price=1300000,
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
            check_in=date(2026, 6, 22),
            check_out=date(2026, 6, 20),
            guest_count=2,
            phone="0909123456",
            total_price=1300000,
        )

    # Invalid guest count
    with pytest.raises(ValueError, match="guest_count must be greater than zero"):
        Booking(
            id=bid,
            conversation_id=cid,
            room_id=rid,
            check_in=date(2026, 6, 20),
            check_out=date(2026, 6, 22),
            guest_count=0,
            phone="0909123456",
            total_price=1300000,
        )
