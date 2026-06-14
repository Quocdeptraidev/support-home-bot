from datetime import date

import pytest

from app.domain.messaging import ExtractedEntities


def test_extracted_entities_accept_valid_booking_data() -> None:
    entities = ExtractedEntities(
        check_in=date(2026, 6, 20),
        check_out=date(2026, 6, 22),
        guest_count=2,
        phone="0909123456",
        room_name="Couple View Vườn",
    )

    assert entities.guest_count == 2
    assert entities.check_out == date(2026, 6, 22)


def test_extracted_entities_reject_invalid_date_range() -> None:
    with pytest.raises(ValueError, match="check_out must be after check_in"):
        ExtractedEntities(
            check_in=date(2026, 6, 22),
            check_out=date(2026, 6, 20),
        )


def test_extracted_entities_reject_invalid_guest_count() -> None:
    with pytest.raises(ValueError, match="guest_count must be greater than zero"):
        ExtractedEntities(guest_count=0)
