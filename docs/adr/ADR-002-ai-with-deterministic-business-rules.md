# ADR-002: AI hỗ trợ, business rules quyết định

- Status: Accepted
- Date: 2026-06-14

## Context

Hội thoại tự nhiên cần AI, nhưng availability, giá và booking không được phụ thuộc
vào output không xác định.

## Decision

AI thực hiện classification, extraction, FAQ và draft reply bằng structured output.
Domain/application service validate output và quyết định mọi side effect nghiệp vụ.

## Consequences

- Cần schema AI rõ ràng và fallback khi confidence thấp.
- Có thể thay model/provider mà không đổi domain rules.
- Test nghiệp vụ không cần gọi AI thật.

