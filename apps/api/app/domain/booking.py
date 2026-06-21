import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime
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
    price_per_hour: int
    capacity: int


@dataclass(frozen=True)
class Booking:
    id: uuid.UUID
    conversation_id: uuid.UUID
    room_id: uuid.UUID
    check_in: datetime
    check_out: datetime
    guest_count: int
    phone: str
    total_price: int
    status: BookingStatus = BookingStatus.PENDING
    google_calendar_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if self.guest_count <= 0:
            raise ValueError("guest_count must be greater than zero")


def is_overnight_booking(check_in: datetime, check_out: datetime) -> bool:
    """
    Xác định xem booking là qua đêm hay theo giờ.
    Nếu check-in và check-out khác ngày hoặc khoảng thời gian từ 12 tiếng trở lên -> Qua đêm.
    """
    if check_out.date() != check_in.date():
        return True
    duration_hours = (check_out - check_in).total_seconds() / 3600.0
    return duration_hours >= 12.0


def calculate_booking_price(room: Room, check_in: datetime, check_out: datetime) -> int:
    """
    Tính tổng giá tiền dựa trên hình thức thuê:
    - Thuê qua đêm: tính theo đêm (tối thiểu 1 đêm).
    - Thuê theo giờ: tính theo giờ (làm tròn lên, tối thiểu 2 giờ).
    """
    if check_out <= check_in:
        raise ValueError("check_out must be after check_in")

    if is_overnight_booking(check_in, check_out):
        nights = (check_out.date() - check_in.date()).days
        if nights == 0:
            nights = 1
        return room.price_per_night * nights
    else:
        duration_seconds = (check_out - check_in).total_seconds()
        hours = math.ceil(duration_seconds / 3600.0)
        if hours < 2:
            hours = 2
        return room.price_per_hour * hours


def calculate_duration_display(check_in: datetime, check_out: datetime) -> str:
    """
    Trả về chuỗi hiển thị thời lượng thuê (ví dụ: "3 tiếng" hoặc "2 đêm").
    """
    if check_out <= check_in:
        raise ValueError("check_out must be after check_in")

    if is_overnight_booking(check_in, check_out):
        nights = (check_out.date() - check_in.date()).days
        if nights == 0:
            nights = 1
        return f"{nights} đêm"
    else:
        duration_seconds = (check_out - check_in).total_seconds()
        hours = math.ceil(duration_seconds / 3600.0)
        if hours < 2:
            hours = 2
        return f"{hours} tiếng"


def check_overlap(b1_in: datetime, b1_out: datetime, b2_in: datetime, b2_out: datetime) -> bool:
    """
    Checks if two datetime ranges overlap.
    """
    return b1_in < b2_out and b2_in < b1_out
