# ADR-003: PostgreSQL cho dữ liệu bền vững, Redis cho trạng thái ngắn hạn

- Status: Accepted
- Date: 2026-06-14

## Decision

PostgreSQL lưu conversation, messages, decisions, escalation và booking. Redis chỉ
dùng cho idempotency, lock, cache, rate limit và queue ngắn hạn.

## Consequences

- Redis có thể bị xóa mà không làm mất dữ liệu nghiệp vụ.
- Mọi state cần audit phải được ghi PostgreSQL.
- Pipeline phải xử lý an toàn khi một trong hai storage tạm thời lỗi.

