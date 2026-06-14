# Database Schema

Schema dưới đây là thiết kế mục tiêu. Mọi thay đổi thực tế phải đi qua Alembic.

## conversations

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| channel | varchar | `facebook` |
| external_user_id | varchar | PSID, index |
| status | varchar | `bot_active`, `human_required`, `closed` |
| last_message_at | timestamptz | index |
| created_at | timestamptz | UTC |
| updated_at | timestamptz | UTC |

Unique: `(channel, external_user_id)`.

## messages

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| conversation_id | UUID | FK, index |
| external_message_id | varchar | Meta MID, unique khi có |
| direction | varchar | `inbound`, `outbound` |
| sender | varchar | `customer`, `bot`, `human` |
| text | text | nội dung đã chuẩn hóa |
| provider_payload | jsonb | payload tối thiểu cần audit |
| delivery_status | varchar | `received`, `sent`, `failed` |
| created_at | timestamptz | UTC |
| updated_at | timestamptz | UTC |

## ai_decisions

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| message_id | UUID | FK, index |
| intent | varchar | index |
| entities | jsonb | dữ liệu trích xuất |
| confidence | numeric | 0..1 |
| needs_human | boolean | index |
| model | varchar | model thực tế đã dùng |
| created_at | timestamptz | UTC |
| updated_at | timestamptz | UTC |

Không lưu chain-of-thought. Chỉ lưu output nghiệp vụ cần audit.

## escalations

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| conversation_id | UUID | FK, index |
| reason | varchar | stable reason code |
| summary | text | nội dung tóm tắt |
| telegram_message_id | varchar | nullable |
| status | varchar | `pending`, `sent`, `failed`, `resolved` |
| created_at | timestamptz | UTC |
| updated_at | timestamptz | UTC |

## rooms và bookings

Giữ thiết kế nghiệp vụ từ master plan nhưng chỉ triển khai sau khi webhook và
conversation pipeline ổn định. `pending` và `confirmed` giữ inventory;
`canceled` không giữ inventory.

## Redis keys

```text
idempotency:facebook:{event_id}       TTL 24h mặc định
lock:conversation:{external_user_id}  TTL ngắn
rate:facebook:{window}:{key}          TTL theo rate window
```

Redis key không chứa token hoặc nội dung message.

