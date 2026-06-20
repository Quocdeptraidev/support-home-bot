# Master Plan: Mây Homestay Facebook Support Bot

> Demo: **Mây Homestay Đà Lạt** - bot hỗ trợ khách trực tiếp trên Facebook
> Messenger, dùng AI để hiểu hội thoại và Telegram để chủ homestay tiếp quản khi
> cần.

---

## 1. Mục tiêu

Xây dựng một demo gần với vận hành thật:

- Khách nhắn trực tiếp vào Facebook Page của Mây Homestay.
- Meta gửi message event về FastAPI webhook.
- AI phân loại ý định, trích xuất thông tin và soạn câu trả lời.
- Business rules kiểm soát giá, phòng trống và booking.
- Bot trả lời khách qua Facebook Messenger Send API.
- Chủ homestay nhận Telegram notification khi cần xác nhận hoặc xử lý thủ công.
- PostgreSQL lưu conversation, message, quyết định AI và booking.
- Redis xử lý event trùng, lock, cache và rate limit.

MVP là backend-only, không chứa source web chat hoặc admin dashboard.

---

## 2. Luồng demo chính

```text
Khách nhắn Facebook Page
        |
        v
Meta Messenger Webhook
        |
        v
FastAPI
  |-- xác minh signature
  |-- bỏ echo/unsupported event
  |-- chống xử lý event trùng bằng Redis
  |-- tải conversation history
  |-- gọi OpenAI
  |-- chạy business rules
        |
        +------> Facebook Send API trả lời khách
        |
        +------> Telegram báo chủ homestay khi cần
        |
        +------> PostgreSQL lưu audit/conversation
```

### Ví dụ

```text
Khách: Cuối tuần này còn phòng cho 2 người không?

AI result:
  intent: booking_inquiry
  guest_count: 2
  check_in: chưa có
  confidence: 0.94

Bot: Dạ mình muốn nhận phòng ngày nào ạ?

Khách: Thứ 7 đến chủ nhật.

Backend:
  - parse ngày theo Asia/Ho_Chi_Minh
  - kiểm tra inventory bằng business rule
  - tính giá deterministic

Bot: Hiện còn Couple View Vườn, giá 650.000đ/đêm.
     Mình có muốn chủ homestay giữ phòng không ạ?

Khách: Có.

Bot: Dạ cho em xin số điện thoại để chủ homestay xác nhận ạ.

Telegram:
  Booking lead mới
  - Khách: Facebook PSID đã che bớt
  - Ngày: ...
  - Số khách: 2
  - Phòng đề xuất: Couple View Vườn
  - SĐT: ...
```

---

## 3. Nguyên tắc sản phẩm

### AI hỗ trợ, không quyết định nghiệp vụ

AI được dùng cho:

- intent classification;
- entity extraction;
- FAQ;
- draft reply;
- tóm tắt escalation.

AI không được tự:

- xác nhận còn phòng;
- tính giá cuối cùng;
- tạo, xác nhận hoặc hủy booking;
- quyết định đã nhận thanh toán.

Các hành động trên phải do application/domain service quyết định.

### Telegram là human escalation

Telegram gửi thông báo khi:

- khách yêu cầu gặp nhân viên;
- khách muốn giữ/đặt phòng;
- AI confidence thấp;
- thiếu dữ liệu hoặc gặp tình huống ngoài phạm vi;
- Facebook, OpenAI hoặc database gặp lỗi cần can thiệp.

Telegram không thay thế phản hồi Messenger.

---

## 4. Tech Stack

| Tầng | Công nghệ |
|---|---|
| API | Python 3.13, FastAPI |
| Database | PostgreSQL 17 |
| ORM/Migration | SQLAlchemy 2 async, Alembic |
| Cache/Idempotency | Redis 8 |
| AI | OpenAI Responses API, model cấu hình qua env |
| Messaging | Meta Messenger Platform / Graph API |
| Escalation | Telegram Bot API |
| HTTP client | HTTPX |
| Validation | Pydantic / Pydantic Settings |
| Quality | Ruff, mypy strict, pytest |
| Local runtime | Docker Compose |

---

## 5. Kiến trúc source

```text
apps/api/app/
├── api/
│   ├── routes/             # health, Facebook webhook
│   ├── dependencies/       # composition root
│   └── schemas/            # HTTP/provider boundary schemas
├── application/
│   ├── use_cases/          # process message, escalation, booking
│   └── errors.py
├── domain/
│   ├── messaging.py        # entities và enums
│   ├── booking.py          # business entities/rules, triển khai sau
│   └── ports.py            # protocol cho adapter
├── infrastructure/
│   ├── ai/                 # OpenAI adapter
│   ├── messaging/          # Meta adapter
│   ├── notifications/      # Telegram adapter
│   ├── persistence/        # SQLAlchemy repositories
│   └── cache/              # Redis idempotency/rate limit
├── core/
│   ├── config.py
│   ├── security.py
│   ├── logging.py
│   └── errors.py
└── main.py
```

Dependency:

```text
api -> application -> domain
infrastructure -------> ports
```

---

## 6. Environment configuration

`.env.example` là danh sách biến chuẩn.

Nhóm cấu hình:

- app/server/timezone;
- PostgreSQL;
- Redis;
- Facebook Page access token, app secret, verify token, API version;
- OpenAI API key và model;
- Telegram bot token/chat ID;
- rate limit và AI safety.

Quy tắc:

- Không commit `.env`.
- Không hardcode token/model/API version.
- `FB_API_VERSION` phải đối chiếu Meta App Dashboard trước khi deploy.
- Healthcheck chạy được khi chưa có provider token.
- Endpoint/provider adapter phải fail rõ ràng nếu integration chưa được cấu hình.

---

## 7. Facebook webhook

### Verification

```http
GET /api/v1/webhooks/facebook
```

- kiểm tra `hub.mode`;
- so sánh `hub.verify_token` bằng constant-time comparison;
- trả `hub.challenge` khi hợp lệ.

### Event callback

```http
POST /api/v1/webhooks/facebook
```

Yêu cầu:

- đọc raw body;
- xác minh `X-Hub-Signature-256` bằng `FB_APP_SECRET`;
- parse JSON sau khi signature hợp lệ;
- bỏ message echo và event chưa hỗ trợ;
- idempotent theo Meta event/message ID;
- acknowledge nhanh;
- không xử lý cùng conversation song song nếu có thể gây đảo thứ tự.

Khi AI/provider xử lý lâu, callback chỉ validate + enqueue; worker xử lý phần còn lại.

---

## 8. AI contract

AI phải trả structured output:

```json
{
  "intent": "booking_inquiry",
  "entities": {
    "check_in": null,
    "check_out": null,
    "guest_count": 2,
    "phone": null
  },
  "draft_reply": "Dạ mình muốn nhận phòng ngày nào ạ?",
  "confidence": 0.94,
  "needs_human": false,
  "escalation_reason": null
}
```

Backend phải:

- validate schema;
- giới hạn conversation history;
- không lưu chain-of-thought;
- không tin entity chưa được business rule kiểm tra;
- fallback + escalation khi provider lỗi hoặc confidence dưới ngưỡng.

---

## 9. Database mục tiêu

### Giai đoạn conversation pipeline

- `conversations`
- `messages`
- `ai_decisions`
- `escalations`

### Giai đoạn booking

- `rooms`
- `bookings`

Quy tắc inventory:

- khoảng ngày dùng `[check_in, check_out)`;
- overlap khi:
  `existing.check_in < requested.check_out`
  và `existing.check_out > requested.check_in`;
- booking `pending` và `confirmed` giữ inventory;
- booking `canceled` không giữ inventory;
- tiền lưu integer VNĐ.

Schema chi tiết: `docs/database-schema.md`.

---

## 10. API scope

| Method | Endpoint | Giai đoạn | Mô tả |
|---|---|---|---|
| GET | `/health` | 1 | process health |
| GET | `/api/v1/webhooks/facebook` | 1 | Meta verification |
| POST | `/api/v1/webhooks/facebook` | 1 | nhận Messenger event |
| GET | `/ready` | 2 | PostgreSQL/Redis readiness |
| GET | `/api/v1/rooms` | 3 | danh sách phòng |
| GET | `/api/v1/rooms/available` | 3 | kiểm tra inventory |
| POST | `/api/v1/bookings` | 3 | tạo booking pending |
| PATCH | `/api/v1/bookings/{id}/status` | 4 | confirm/cancel |

---

## 11. Roadmap

### Sprint 0 - Foundation

- [x] Chốt Facebook-first architecture.
- [x] Tạo `AGENTS.md` và tài liệu kỹ thuật.
- [x] Setup FastAPI, PostgreSQL, Redis và Docker Compose.
- [x] Setup Pydantic Settings cho Facebook/OpenAI/Telegram.
- [x] Tạo Clean Architecture source skeleton.
- [x] Implement webhook verification và signature utility.
- [x] Build image, chạy Ruff, mypy và pytest.

### Sprint 1 - Facebook webhook end-to-end

- [x] Thêm `POST /api/v1/webhooks/facebook`.
- [x] Parse Meta Page message event.
- [x] Bỏ echo/unsupported event.
- [x] Redis idempotency theo message/event ID.
- [x] Conversation lock.
- [x] Meta Send API adapter.
- [x] Unit/integration tests cho webhook.
- [x] Dùng tunnel HTTPS để Meta gọi môi trường local.

### Sprint 2 - AI và Telegram escalation

- [x] OpenAI Responses API adapter.
- [x] Structured output schema.
- [x] Conversation history repository.
- [x] Confidence và safety fallback.
- [x] Telegram notifier.
- [x] FAQ và booking-intent demo.
- [x] Test timeout/provider failure.

### Sprint 3 - Room và booking rules

- [x] Migration `rooms` và seed ba loại phòng.
- [x] Migration `bookings`.
- [x] Availability service.
- [x] Price calculation cho room/person.
- [x] Booking lead/pending workflow.
- [x] Telegram booking summary.

### Sprint 4 - Hardening demo

- [ ] Structured logging và request correlation.
- [ ] Rate limiting.
- [ ] Readiness endpoint.
- [ ] Retry/backoff và delivery audit.
- [ ] Ba demo scripts cố định.
- [ ] Deploy backend + PostgreSQL + Redis.
- [ ] Meta App production checklist.

### Giai đoạn sau

- [ ] Admin dashboard.
- [ ] Human takeover UI.
- [ ] Instagram messaging.
- [ ] Multi-homestay/tenant.
- [ ] Analytics và reporting.

---

## 12. Ba kịch bản demo bắt buộc

1. **FAQ thành công**

   Khách hỏi giờ check-in hoặc tiện nghi, bot trả lời trên Messenger.

2. **Booking lead và escalation**

   Khách cung cấp ngày/số người/SĐT, backend kiểm tra rule và Telegram báo chủ nhà.

3. **Fallback an toàn**

   AI lỗi hoặc confidence thấp, bot xin phép chuyển nhân viên và Telegram nhận cảnh báo.

---

## 13. Definition of Done

- Webhook signature và verify token được kiểm tra.
- Event trùng không tạo side effect lần hai.
- Provider calls có timeout và lỗi được chuyển thành internal error.
- AI output được validate.
- Không có token/secret trong log hoặc git.
- Ruff, mypy và pytest đều qua.
- Tài liệu architecture, API contract và schema đúng với code.

---

*Master plan cập nhật ngày 14/06/2026 cho hướng Facebook Messenger + AI + Telegram.*
