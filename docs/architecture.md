# Kiến trúc hệ thống

## Mục tiêu

Nhận tin nhắn từ Facebook Page, xử lý an toàn và idempotent, trả lời qua Messenger,
đồng thời báo Telegram khi chủ homestay cần tiếp quản.

## Context

```text
Khách
  |
Facebook Messenger
  |
Meta Webhook ----> FastAPI ----> Meta Send API
                       |
                       +-------> OpenAI Responses API
                       |
                       +-------> Telegram Bot API
                       |
                 PostgreSQL + Redis
```

## Container

### FastAPI

- xác minh subscription và chữ ký webhook;
- chuẩn hóa Meta event thành domain message;
- điều phối AI, business rules và provider adapters;
- cung cấp health/readiness endpoint.

### PostgreSQL

- conversation và message history;
- customer/contact mapping;
- booking và room data khi nghiệp vụ booking được triển khai;
- audit trạng thái escalation.

### Redis

- idempotency theo Meta event/message ID;
- distributed lock theo conversation;
- rate limit;
- queue/cache ngắn hạn khi cần.

Redis không phải nguồn dữ liệu bền vững.

## Luồng xử lý message

1. Meta gọi `POST /api/v1/webhooks/facebook`.
2. API đọc raw body và xác minh `X-Hub-Signature-256`.
3. Adapter parse event, bỏ echo/unsupported event.
4. Redis claim event ID; event trùng được acknowledge nhưng không xử lý lại.
5. Use case tải conversation history giới hạn.
6. AI trả structured result gồm intent, entities, draft reply, confidence và cờ escalation.
7. Application/domain rules validate và quyết định hành động.
8. Messenger adapter gửi phản hồi.
9. Nếu cần người xử lý, Telegram adapter gửi tóm tắt.
10. PostgreSQL lưu message, decision và trạng thái gửi.

Webhook cần acknowledge nhanh. Khi thời gian xử lý vượt ngưỡng ổn định, bước 5-10
được chuyển sang worker; HTTP callback chỉ validate, enqueue và trả `200`.

## Layer và dependency

```text
api -> application -> domain
infrastructure -------> domain/application ports
```

- `domain`: không import framework/provider.
- `application`: điều phối use case qua protocol.
- `infrastructure`: hiện thực protocol bằng SDK/HTTP/database.
- `api`: chuyển đổi HTTP input/output và composition root.

## Failure strategy

- Chữ ký sai: `401`, không xử lý.
- Event trùng: `200`, không side effect.
- OpenAI timeout: fallback an toàn và Telegram escalation.
- Meta Send API lỗi tạm thời: retry có giới hạn; lưu trạng thái failed.
- Telegram lỗi: log/audit nhưng không làm gửi Messenger bị lặp.
- PostgreSQL lỗi: không xác nhận nghiệp vụ chưa được lưu.

## Security

- Token chỉ lấy từ Settings và secret store ở production.
- So sánh signature/verify token bằng constant-time comparison.
- Log masking cho PSID và dữ liệu nhạy cảm.
- Giới hạn payload và conversation history.
- Không tin AI output cho quyết định booking hoặc giá.

## Thành phần ngoài phạm vi backend demo

- web chat giả lập;
- admin dashboard;
- Facebook/Instagram đa kênh;
- worker queue riêng;
- human takeover UI.
