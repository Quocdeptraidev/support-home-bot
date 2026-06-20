import uuid
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class Room:
    id: uuid.UUID
    name: str
    price_per_night: int
    capacity: int


@dataclass(frozen=True)
class Booking:
    id: uuid.UUID
    conversation_id: uuid.UUID
    room_id: uuid.UUID
    check_in: date
    check_out: date
    guest_count: int
    phone: str
    total_price: int
    status: BookingStatus = BookingStatus.PENDING

    def __post_init__(self) -> None:
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if self.guest_count <= 0:
            raise ValueError("guest_count must be greater than zero")


def calculate_nights(check_in: date, check_out: date) -> int:
    if check_out <= check_in:
        raise ValueError("check_out must be after check_in")
    return (check_out - check_in).days


def calculate_total_price(price_per_night: int, nights: int) -> int:
    if price_per_night < 0 or nights < 0:
        raise ValueError("price_per_night and nights must be non-negative")
    return price_per_night * nights


def check_overlap(b1_in: date, b1_out: date, b2_in: date, b2_out: date) -> bool:
    """
    Checks if two date ranges overlap.
    Ranges are half-open interval: [check_in, check_out).
    """
    return b1_in < b2_out and b2_in < b1_out
