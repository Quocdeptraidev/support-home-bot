# ADR-001: Facebook-first MVP

- Status: Accepted
- Date: 2026-06-14

## Context

Kế hoạch ban đầu ưu tiên web chat và dashboard trước khi tích hợp Meta. Người dùng
đã có Facebook Page demo, cấu hình webhook/model AI và Telegram.

## Decision

Đưa Facebook Messenger webhook lên critical path. Web chat và dashboard tạm hoãn.
MVP tập trung vào pipeline Facebook -> AI/business rules -> Facebook/Telegram.

## Consequences

- Demo gần môi trường thật hơn và giảm frontend scope.
- Phải xử lý signature, idempotency, rate limit và provider failures từ đầu.
- Human escalation có thể dùng Telegram trước khi có admin UI.

