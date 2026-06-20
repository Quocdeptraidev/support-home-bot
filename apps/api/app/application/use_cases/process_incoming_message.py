import uuid

from app.application.errors import AIProviderError
from app.domain.booking import (
    Booking,
    BookingStatus,
    calculate_nights,
    calculate_total_price,
    check_overlap,
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
    ConversationRepository,
    EscalationNotifier,
    IdempotencyStore,
    MessageGateway,
    RoomRepository,
)

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
        history_limit: int,
        idempotency_ttl_seconds: int,
        escalation_threshold: float,
    ) -> None:
        self._ai_responder = ai_responder
        self._conversation_repository = conversation_repository
        self._idempotency_store = idempotency_store
        self._message_gateway = message_gateway
        self._escalation_notifier = escalation_notifier
        self._room_repository = room_repository
        self._booking_repository = booking_repository
        self._history_limit = history_limit
        self._idempotency_ttl_seconds = idempotency_ttl_seconds
        self._escalation_threshold = escalation_threshold

    async def execute(self, message: IncomingMessage) -> ProcessMessageResult:
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

        try:
            decision = await self._ai_responder.analyze(message, history)
        except AIProviderError:
            decision = AIDecision(
                intent=Intent.UNKNOWN,
                draft_reply=FALLBACK_REPLY,
                confidence=0,
                needs_human=True,
                escalation_reason=EscalationReason.AI_PROVIDER_FAILURE,
            )

        reply = decision.draft_reply.strip() or FALLBACK_REPLY
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
                        nights = calculate_nights(check_in, check_out)
                        total = calculate_total_price(requested_room.price_per_night, nights)
                        reply = (
                            f"Dạ hiện bên em còn phòng {requested_room.name}, "
                            f"giá {requested_room.price_per_night:,}đ/đêm "
                            f"(tổng {total:,}đ cho {nights} đêm). "
                            f"Mình có muốn giữ phòng không ạ?"
                        ).replace(",", ".")
                    else:
                        # Check if room exists but is not available (occupied or capacity too small)
                        all_rooms = await self._room_repository.get_all()
                        room_exists = any(
                            r.name.lower() == entities.room_name.lower() for r in all_rooms
                        )
                        if room_exists:
                            if available_rooms:
                                room_list_str = ", ".join(
                                    [
                                        f"{r.name} ({r.price_per_night:,}đ/đêm)".replace(",", ".")
                                        for r in available_rooms
                                    ]
                                )
                                reply = (
                                    f"Dạ tiếc quá, phòng {entities.room_name} đã hết "
                                    f"(hoặc không đủ sức chứa) trong thời gian này rồi ạ. "
                                    f"Nhưng bên em vẫn còn các phòng khác: {room_list_str}. "
                                    f"Mình có muốn tham khảo không ạ?"
                                )
                            else:
                                reply = (
                                    "Dạ hiện tại khoảng thời gian này bên em đã hết phòng rồi ạ. "
                                    "Mình có muốn chọn ngày khác không ạ?"
                                )
                        else:
                            # Requested room doesn't exist, list available
                            if available_rooms:
                                room_list_str = ", ".join(
                                    [
                                        f"{r.name} ({r.price_per_night:,}đ/đêm)".replace(",", ".")
                                        for r in available_rooms
                                    ]
                                )
                                reply = (
                                    f"Dạ tiếc quá, bên em không có phòng {entities.room_name} ạ. "
                                    f"Nhưng bên em hiện đang còn phòng: {room_list_str}. "
                                    f"Mình có muốn tham khảo không ạ?"
                                )
                            else:
                                reply = (
                                    "Dạ hiện tại khoảng thời gian này bên em đã hết phòng rồi ạ. "
                                    "Mình có muốn chọn ngày khác không ạ?"
                                )
                else:
                    if available_rooms:
                        room_list_str = ", ".join(
                            [
                                f"{r.name} ({r.price_per_night:,}đ/đêm)".replace(",", ".")
                                for r in available_rooms
                            ]
                        )
                        reply = (
                            f"Dạ trong khoảng thời gian từ {check_in} đến {check_out}, "
                            f"bên em còn các phòng: {room_list_str}. "
                            f"Mình có muốn đặt phòng nào không ạ?"
                        )
                    else:
                        reply = (
                            "Dạ hiện tại khoảng thời gian này bên em đã hết phòng rồi ạ. "
                            "Mình có muốn chọn ngày khác không ạ?"
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
                reply = (
                    f"Dạ bên em không tìm thấy phòng nào tên là {room_name} ạ. "
                    f"Anh/chị có muốn chọn phòng khác không?"
                )
            else:
                # Check availability
                bookings = await self._booking_repository.get_active_bookings_by_room(room.id)
                is_available = not any(
                    check_overlap(b.check_in, b.check_out, check_in, check_out) for b in bookings
                )
                if not is_available:
                    reply = (
                        f"Dạ tiếc quá, phòng {room.name} vừa mới bị đặt trùng lịch mất rồi ạ. "
                        f"Anh/chị có muốn tham khảo ngày khác hoặc phòng khác không ạ?"
                    )
                elif guest_count > room.capacity:
                    reply = (
                        f"Dạ tiếc quá, phòng {room.name} chỉ có sức chứa "
                        f"tối đa {room.capacity} khách thôi ạ. "
                        f"Anh/chị có muốn chọn phòng khác lớn hơn không?"
                    )
                else:
                    # Success: Create PENDING booking
                    nights = calculate_nights(check_in, check_out)
                    total = calculate_total_price(room.price_per_night, nights)
                    conv_id = await self._conversation_repository.get_conversation_id(
                        message.sender_id
                    )

                    if conv_id is None:
                        conv_id = uuid.uuid4()

                    booking = Booking(
                        id=uuid.uuid4(),
                        conversation_id=conv_id,
                        room_id=room.id,
                        check_in=check_in,
                        check_out=check_out,
                        guest_count=guest_count,
                        phone=phone,
                        total_price=total,
                        status=BookingStatus.PENDING,
                    )
                    await self._booking_repository.create(booking)

                    reply = (
                        f"Dạ em đã ghi nhận thông tin đặt phòng {room.name} "
                        f"từ ngày {check_in} đến ngày {check_out} cho {guest_count} người. "
                        f"Em đã chuyển thông tin cho chủ homestay xác nhận và liên hệ lại "
                        f"với mình qua số {phone} sớm nhất có thể ạ."
                    )
                    should_escalate = True
                    escalation_reason = EscalationReason.BOOKING_REQUIRES_CONFIRMATION
                    escalation_summary = (
                        f"Khách đặt phòng {room.name}\n"
                        f"- Ngày: {check_in} -> {check_out} ({nights} đêm)\n"
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
                )
            )

        return ProcessMessageResult(
            duplicate=False,
            reply_sent=True,
            escalated=should_escalate,
        )
