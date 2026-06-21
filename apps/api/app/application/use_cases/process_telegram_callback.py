import logging
import uuid
from app.domain.booking import BookingStatus
from app.domain.ports import (
    BookingRepository,
    CalendarGateway,
    ConversationRepository,
    EscalationNotifier,
    MessageGateway,
    RoomRepository,
)

logger = logging.getLogger(__name__)


class ProcessTelegramCallback:
    def __init__(
        self,
        *,
        booking_repository: BookingRepository,
        room_repository: RoomRepository,
        conversation_repository: ConversationRepository,
        calendar_gateway: CalendarGateway,
        message_gateway: MessageGateway,
        escalation_notifier: EscalationNotifier,
    ) -> None:
        self._booking_repository = booking_repository
        self._room_repository = room_repository
        self._conversation_repository = conversation_repository
        self._calendar_gateway = calendar_gateway
        self._message_gateway = message_gateway
        self._escalation_notifier = escalation_notifier

    async def execute(
        self,
        *,
        callback_query_id: str,
        chat_id: str,
        message_id: str,
        message_text: str,
        callback_data: str,
    ) -> bool:
        # callback_data có dạng: "confirm_booking:<booking_id>" hoặc "cancel_booking:<booking_id>"
        if not (callback_data.startswith("confirm_booking:") or callback_data.startswith("cancel_booking:")):
            logger.warning("Invalid callback data: %s", callback_data)
            await self._escalation_notifier.answer_callback_query(
                callback_query_id=callback_query_id,
                text="Lỗi: Dữ liệu callback không hợp lệ!",
            )
            return False

        parts = callback_data.split(":", 1)
        action = parts[0]
        try:
            booking_id = uuid.UUID(parts[1])
        except ValueError:
            logger.error("Failed to parse booking ID from callback data: %s", callback_data)
            await self._escalation_notifier.answer_callback_query(
                callback_query_id=callback_query_id,
                text="Lỗi: ID đặt phòng không hợp lệ!",
            )
            return False

        logger.info(
            "Processing Telegram callback action '%s' for Booking ID: %s",
            action,
            booking_id,
        )

        booking = await self._booking_repository.get_by_id(booking_id)
        if not booking:
            logger.warning("Booking not found: %s", booking_id)
            await self._escalation_notifier.answer_callback_query(
                callback_query_id=callback_query_id,
                text="Lỗi: Không tìm thấy thông tin đặt phòng này!",
            )
            return False

        if booking.status != BookingStatus.PENDING:
            logger.warning("Booking %s is already %s", booking_id, booking.status)
            status_desc = "đã xác nhận" if booking.status == BookingStatus.CONFIRMED else "đã hủy"
            await self._escalation_notifier.answer_callback_query(
                callback_query_id=callback_query_id,
                text=f"Thông báo: Đơn đặt phòng này đã {status_desc} trước đó!",
            )
            return False

        room = await self._room_repository.get_by_id(booking.room_id)
        room_name = room.name if room else "Phòng"

        new_status = BookingStatus.CONFIRMED if action == "confirm_booking" else BookingStatus.CANCELED
        
        # 1. Cập nhật booking trong DB
        updated_booking = booking.__class__(
            id=booking.id,
            conversation_id=booking.conversation_id,
            room_id=booking.room_id,
            check_in=booking.check_in,
            check_out=booking.check_out,
            guest_count=booking.guest_count,
            phone=booking.phone,
            total_price=booking.total_price,
            status=new_status,
            google_calendar_event_id=booking.google_calendar_event_id,
        )
        await self._booking_repository.update(updated_booking)
        logger.info("Updated booking %s status to %s", booking_id, new_status.value)

        # 2. Cập nhật Google Calendar
        if booking.google_calendar_event_id:
            status_tag = "[ĐẶT PHÒNG CONFIRMED]" if new_status == BookingStatus.CONFIRMED else "[ĐẶT PHÒNG CANCELED]"
            new_title = f"{status_tag} {room_name} - SĐT: {booking.phone}"
            cal_color = "10" if new_status == BookingStatus.CONFIRMED else "8"
            await self._calendar_gateway.update_event_title(
                event_id=booking.google_calendar_event_id,
                new_title=new_title,
                color_id=cal_color,
            )
            logger.info("Updated Google Calendar event title for event %s", booking.google_calendar_event_id)

        # 3. Gửi tin nhắn Facebook Messenger cho khách hàng
        psid = await self._conversation_repository.get_external_user_id(booking.conversation_id)
        if psid:
            if new_status == BookingStatus.CONFIRMED:
                messenger_reply = (
                    f"Dạ, Mây Homestay xin thông báo: Yêu cầu đặt phòng {room_name} của bạn "
                    f"đã được xác nhận thành công! Hẹn gặp bạn vào ngày nhận phòng nhé. 🥰❤️"
                )
            else:
                messenger_reply = (
                    f"Dạ, Mây Homestay rất tiếc phải thông báo: Yêu cầu đặt phòng {room_name} của bạn "
                    f"đã bị hủy. Bạn vui lòng liên hệ lại homestay nếu cần hỗ trợ thêm nhé!"
                )
            try:
                await self._message_gateway.send_text(psid, messenger_reply)
                await self._conversation_repository.append_bot_reply(psid, messenger_reply)
                logger.info("Sent confirmation message to customer via Facebook Messenger (PSID: %s)", psid)
            except Exception as e:
                logger.error("Failed to send Messenger notification to customer: %s", e)

        # 4. Sửa tin nhắn Telegram để cập nhật trạng thái mới và xóa nút bấm
        status_text = "<b>ĐÃ XÁC NHẬN ✅</b>" if new_status == BookingStatus.CONFIRMED else "<b>ĐÃ HỦY ❌</b>"
        
        # Tạo tin nhắn mới bằng cách ghép trạng thái vào nội dung cũ
        # Để tránh tin nhắn bị lặp, ta có thể sửa dòng đầu tiên hoặc nối thêm dòng trạng thái
        lines = message_text.split("\n")
        if lines and "CẦN CAN THIỆP" in lines[0]:
            lines[0] = f"✅ <b>ĐÃ XỬ LÝ - {status_text}</b>"
        else:
            lines.insert(0, f"✅ <b>ĐÃ XỬ LÝ - {status_text}</b>\n")
            
        new_message_text = "\n".join(lines)
        
        await self._escalation_notifier.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            new_text=new_message_text,
        )

        # 5. Phản hồi popup cho người dùng Telegram bấm nút
        popup_text = "Đã xác nhận đặt phòng thành công!" if new_status == BookingStatus.CONFIRMED else "Đã hủy đơn đặt phòng!"
        await self._escalation_notifier.answer_callback_query(
            callback_query_id=callback_query_id,
            text=popup_text,
        )

        return True
