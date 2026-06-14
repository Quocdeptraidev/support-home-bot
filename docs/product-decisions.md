# Product Decisions

## Trạng thái hiện hành

Các quyết định trong tài liệu này đã được hợp nhất vào
`master-plan-bot-homestay.md`. File này giữ phần tóm tắt để tra cứu nhanh.

## MVP

1. Dùng Facebook Page thật làm kênh demo thay vì web chat giả lập.
2. FastAPI nhận Meta webhook và trả lời qua Messenger Send API.
3. OpenAI hỗ trợ hiểu nội dung và draft reply.
4. Business rules giữ quyền quyết định availability, giá và booking.
5. Telegram báo chủ homestay khi khách cần xác nhận hoặc bot không chắc chắn.
6. PostgreSQL lưu conversation/audit; Redis xử lý idempotency và rate limit.
7. Project backend-only; không giữ source admin dashboard hoặc web chat.

## Non-goals của vòng đầu

- Không tự động xác nhận booking khi chưa có inventory service.
- Không xây UI quản trị.
- Không hỗ trợ Instagram.
- Không huấn luyện model riêng.
- Không gửi dữ liệu khách không cần thiết tới AI.

## Tiêu chí demo đầu tiên

1. Meta xác minh webhook thành công.
2. Một tin nhắn Facebook được nhận đúng một lần.
3. Bot gửi được phản hồi FAQ an toàn.
4. Ý định booking tạo Telegram escalation.
5. Lỗi OpenAI tạo fallback và escalation thay vì im lặng.
