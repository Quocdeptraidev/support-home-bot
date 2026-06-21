import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.application.errors import AIProviderError
from app.domain.booking import (
    Booking,
    BookingStatus,
    calculate_booking_price,
    calculate_duration_display,
    check_overlap,
    is_overnight_booking,
)
from app.domain.messaging import (
    AIDecision,
    EscalationNotice,
    EscalationReason,
    IncomingMessage,
    Intent,
    ProcessMessageResult,
)
from app.domain.ports import (
    AIResponder,
    BookingRepository,
    CalendarGateway,
    ConversationRepository,
    EscalationNotifier,
    IdempotencyStore,
    MessageGateway,
    RoomRepository,
)


def format_datetime(dt: datetime) -> str:
    dt_local = dt.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    if dt_local.minute == 0:
        return dt_local.strftime("%Hh %d/%m")
    return dt_local.strftime("%H:%M %d/%m")


FALLBACK_REPLY = "Dạ em đã nhận được tin nhắn. Chủ homestay sẽ phản hồi mình sớm nhất có thể ạ."


class ProcessIncomingMessage:
    def __init__(
        self,
        *,
        ai_responder: AIResponder,
        conversation_repository: ConversationRepository,
        idempotency_store: IdempotencyStore,
        message_gateway: MessageGateway,
        escalation_notifier: EscalationNotifier,
        room_repository: RoomRepository,
        booking_repository: BookingRepository,
        calendar_gateway: CalendarGateway,
        history_limit: int,
        idempotency_ttl_seconds: int,
        escalation_threshold: float,
        prompts: dict[str, str] | None = None,
    ) -> None:
        self._ai_responder = ai_responder
        self._conversation_repository = conversation_repository
        self._idempotency_store = idempotency_store
        self._message_gateway = message_gateway
        self._escalation_notifier = escalation_notifier
        self._room_repository = room_repository
        self._booking_repository = booking_repository
        self._calendar_gateway = calendar_gateway
        self._history_limit = history_limit
        self._idempotency_ttl_seconds = idempotency_ttl_seconds
        self._escalation_threshold = escalation_threshold
        self._prompts = prompts or {}

    async def execute(self, message: IncomingMessage) -> ProcessMessageResult:
        booking_id = None
        claimed = await self._idempotency_store.claim(
            message.event_id,
            self._idempotency_ttl_seconds,
        )
        if not claimed:
            return ProcessMessageResult(duplicate=True, reply_sent=False, escalated=False)

        history = await self._conversation_repository.get_recent(
            message.sender_id,
            self._history_limit,
        )
        await self._conversation_repository.append_incoming(message)

        fallback_reply = self._prompts.get("fallback_reply", FALLBACK_REPLY)

        try:
            decision = await self._ai_responder.analyze(message, history)
        except AIProviderError:
            decision = AIDecision(
                intent=Intent.UNKNOWN,
                draft_reply=fallback_reply,
                confidence=0,
                needs_human=True,
                escalation_reason=EscalationReason.AI_PROVIDER_FAILURE,
            )

        reply = decision.draft_reply.strip() or fallback_reply
        is_booking_confirmation = decision.intent is Intent.BOOKING_CONFIRMATION
        should_escalate = (
            is_booking_confirmation
            or decision.needs_human
            or decision.confidence < self._escalation_threshold
        )
        escalation_reason = decision.escalation_reason
        escalation_summary = message.text
        entities = decision.entities

        # Business Rules Integration for Booking Inquiry
        if decision.intent == Intent.BOOKING_INQUIRY:
            if (
                entities.check_in is not None
                and entities.check_out is not None
                and entities.guest_count is not None
            ):
                check_in = entities.check_in
                check_out = entities.check_out
                guest_count = entities.guest_count

                rooms = await self._room_repository.get_all()
                available_rooms = []
                for r in rooms:
                    if r.capacity >= guest_count:
                        bookings = await self._booking_repository.get_active_bookings_by_room(r.id)
                        if not any(
                            check_overlap(b.check_in, b.check_out, check_in, check_out)
                            for b in bookings
                        ):
                            available_rooms.append(r)

                is_overnight = is_overnight_booking(check_in, check_out)
                if is_overnight:

                    def get_room_price_str(r):
                        return f"{r.name} ({r.price_per_night:,}đ/đêm)".replace(",", ".")
                else:

                    def get_room_price_str(r):
                        return f"{r.name} ({r.price_per_hour:,}đ/giờ)".replace(",", ".")

                if entities.room_name:
                    requested_room = next(
                        (
                            r
                            for r in available_rooms
                            if r.name.lower() == entities.room_name.lower()
                        ),
                        None,
                    )
                    if requested_room:
                        total = calculate_booking_price(requested_room, check_in, check_out)
                        duration_display = calculate_duration_display(check_in, check_out)
                        if is_overnight:
                            price_display = f"{requested_room.price_per_night:,}đ/đêm".replace(
                                ",", "."
                            )
                        else:
                            price_display = f"{requested_room.price_per_hour:,}đ/giờ".replace(
                                ",", "."
                            )
                        tpl = self._prompts.get(
                            "room_available",
                            "Dạ hiện bên em còn phòng {room_name}, giá {price_display} (tổng {total_price}đ cho {duration_display}). Mình có muốn giữ phòng không ạ?",
                        )
                        reply = tpl.format(
                            room_name=requested_room.name,
                            price_display=price_display,
                            total_price=f"{total:,}".replace(",", "."),
                            duration_display=duration_display,
                        )
                    else:
                        # Check if room exists but is not available (occupied or capacity too small)
                        all_rooms = await self._room_repository.get_all()
                        room_exists = any(
                            r.name.lower() == entities.room_name.lower() for r in all_rooms
                        )
                        if room_exists:
                            if available_rooms:
                                room_list_str = ", ".join(
                                    [get_room_price_str(r) for r in available_rooms]
                                )
                                tpl = self._prompts.get(
                                    "room_occupied_list_others",
                                    "Dạ tiếc quá, phòng {room_name} đã hết (hoặc không đủ sức chứa) trong thời gian này rồi ạ. Nhưng bên em vẫn còn các phòng khác: {room_list_str}. Mình có muốn tham khảo không ạ?",
                                )
                                reply = tpl.format(
                                    room_name=entities.room_name, room_list_str=room_list_str
                                )
                            else:
                                reply = self._prompts.get(
                                    "room_occupied_no_others",
                                    "Dạ hiện tại khoảng thời gian này bên em đã hết phòng rồi ạ. Mình có muốn chọn ngày khác không ạ?",
                                )
                        else:
                            # Requested room doesn't exist, list available
                            if available_rooms:
                                room_list_str = ", ".join(
                                    [get_room_price_str(r) for r in available_rooms]
                                )
                                tpl = self._prompts.get(
                                    "room_not_exist_list_others",
                                    "Dạ tiếc quá, bên em không có phòng {room_name} ạ. Nhưng bên em hiện đang còn phòng: {room_list_str}. Mình có muốn tham khảo không ạ?",
                                )
                                reply = tpl.format(
                                    room_name=entities.room_name, room_list_str=room_list_str
                                )
                            else:
                                reply = self._prompts.get(
                                    "room_not_exist_no_others",
                                    "Dạ hiện tại khoảng thời gian này bên em đã hết phòng rồi ạ. Mình có muốn chọn ngày khác không ạ?",
                                )
                else:
                    if available_rooms:
                        room_list_str = ", ".join([get_room_price_str(r) for r in available_rooms])
                        tpl = self._prompts.get(
                            "inquiry_available_rooms",
                            "Dạ trong khoảng thời gian từ {check_in} đến {check_out}, bên em còn các phòng: {room_list_str}. Mình có muốn đặt phòng nào không ạ?",
                        )
                        reply = tpl.format(
                            check_in=format_datetime(check_in),
                            check_out=format_datetime(check_out),
                            room_list_str=room_list_str,
                        )
                    else:
                        reply = self._prompts.get(
                            "inquiry_no_rooms",
                            "Dạ hiện tại khoảng thời gian này bên em đã hết phòng rồi ạ. Mình có muốn chọn ngày khác không ạ?",
                        )

        # Business Rules Integration for Booking Confirmation
        elif (
            decision.intent == Intent.BOOKING_CONFIRMATION
            and entities.check_in is not None
            and entities.check_out is not None
            and entities.guest_count is not None
            and entities.phone is not None
            and entities.room_name is not None
        ):
            check_in = entities.check_in
            check_out = entities.check_out
            guest_count = entities.guest_count
            phone = entities.phone
            room_name = entities.room_name

            room = await self._room_repository.get_by_name(room_name)
            if not room:
                tpl = self._prompts.get(
                    "confirm_room_not_found",
                    "Dạ bên em không tìm thấy phòng nào tên là {room_name} ạ. Anh/chị có muốn chọn phòng khác không?",
                )
                reply = tpl.format(room_name=room_name)
            else:
                # Check availability
                bookings = await self._booking_repository.get_active_bookings_by_room(room.id)
                is_available = not any(
                    check_overlap(b.check_in, b.check_out, check_in, check_out) for b in bookings
                )
                if not is_available:
                    tpl = self._prompts.get(
                        "confirm_room_occupied",
                        "Dạ tiếc quá, phòng {room_name} vừa mới bị đặt trùng lịch mất rồi ạ. Anh/chị có muốn tham khảo ngày khác hoặc phòng khác không ạ?",
                    )
                    reply = tpl.format(room_name=room.name)
                elif guest_count > room.capacity:
                    tpl = self._prompts.get(
                        "confirm_capacity_exceeded",
                        "Dạ tiếc quá, phòng {room_name} chỉ có sức chứa tối đa {capacity} khách thôi ạ. Anh/chị có muốn chọn phòng khác lớn hơn không?",
                    )
                    reply = tpl.format(room_name=room.name, capacity=room.capacity)
                else:
                    # Success: Create PENDING booking
                    total = calculate_booking_price(room, check_in, check_out)
                    duration_display = calculate_duration_display(check_in, check_out)
                    conv_id = await self._conversation_repository.get_conversation_id(
                        message.sender_id
                    )

                    if conv_id is None:
                        conv_id = uuid.uuid4()

                    booking_id = uuid.uuid4()

                    # Tự động điền Google Calendar trước
                    calendar_title = f"[ĐẶT PHÒNG PENDING] {room.name} - SĐT: {phone}"
                    calendar_desc = (
                        f"Chi tiết đặt phòng:\n"
                        f"- Phòng: {room.name}\n"
                        f"- Số khách: {guest_count}\n"
                        f"- SĐT khách: {phone}\n"
                        f"- Tổng tiền: {total:,} VNĐ\n"
                        f"- Trạng thái: PENDING (Chờ xác nhận)\n"
                        f"- Booking ID: {booking_id}"
                    ).replace(",", ".")
                    
                    event_id = await self._calendar_gateway.create_event(
                        title=calendar_title,
                        start_time=check_in,
                        end_time=check_out,
                        description=calendar_desc,
                        color_id="4",  # Flamingo (Hồng nhạt) đại diện cho trạng thái PENDING
                    )

                    booking = Booking(
                        id=booking_id,
                        conversation_id=conv_id,
                        room_id=room.id,
                        check_in=check_in,
                        check_out=check_out,
                        guest_count=guest_count,
                        phone=phone,
                        total_price=total,
                        status=BookingStatus.PENDING,
                        google_calendar_event_id=event_id,
                    )
                    await self._booking_repository.create(booking)

                    tpl = self._prompts.get(
                        "confirm_success",
                        "Dạ em đã ghi nhận thông tin đặt phòng {room_name} từ ngày {check_in} đến ngày {check_out} cho {guest_count} người. Em đã chuyển thông tin cho chủ homestay xác nhận và liên hệ lại với mình qua số {phone} sớm nhất có thể ạ.",
                    )
                    reply = tpl.format(
                        room_name=room.name,
                        check_in=format_datetime(check_in),
                        check_out=format_datetime(check_out),
                        guest_count=guest_count,
                        phone=phone,
                    )
                    should_escalate = True
                    escalation_reason = EscalationReason.BOOKING_REQUIRES_CONFIRMATION
                    check_in_str = format_datetime(check_in)
                    check_out_str = format_datetime(check_out)
                    escalation_summary = (
                        f"Khách đặt phòng {room.name}\n"
                        f"- Thời gian: {check_in_str} -> {check_out_str} ({duration_display})\n"
                        f"- Số khách: {guest_count}\n"
                        f"- SĐT: {phone}\n"
                        f"- Tổng tiền: {total:,} VNĐ".replace(",", ".")
                    )

        await self._message_gateway.send_text(message.sender_id, reply)
        await self._conversation_repository.append_bot_reply(message.sender_id, reply)

        if should_escalate:
            if escalation_reason is not None:
                reason = escalation_reason
            elif is_booking_confirmation:
                reason = EscalationReason.BOOKING_REQUIRES_CONFIRMATION
            else:
                reason = EscalationReason.LOW_AI_CONFIDENCE
            await self._escalation_notifier.notify(
                EscalationNotice(
                    sender_id=message.sender_id,
                    reason=reason,
                    summary=escalation_summary,
                    booking_id=booking_id,
                )
            )

        return ProcessMessageResult(
            duplicate=False,
            reply_sent=True,
            escalated=should_escalate,
        )
