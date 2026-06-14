# Coding Standards

## Python

- Python 3.13, type hints bắt buộc cho application code.
- Ruff chịu trách nhiệm format, imports và lint.
- mypy chạy strict cho `app`.
- Dùng `async` cho database và network I/O; không biến CPU-bound code thành async.
- Dùng dataclass/domain type cho core model; Pydantic dành cho settings và HTTP/provider schema.

## Module boundaries

- Route không gọi SQLAlchemy/Redis/OpenAI/Meta trực tiếp.
- Use case chỉ phụ thuộc protocol.
- Infrastructure adapter không quyết định nghiệp vụ.
- Mapping provider payload đặt cạnh adapter, không rò payload Meta vào domain.

## Dependency injection

Dependency truyền qua constructor. Composition root tạo concrete adapter:

```python
use_case = ProcessIncomingMessage(
    ai_responder=openai_adapter,
    message_gateway=messenger_adapter,
    notifier=telegram_adapter,
)
```

Không gọi `SessionLocal()`, `OpenAI()` hoặc `httpx.AsyncClient()` trong use case.

## Errors

- Domain/application dùng exception có code ổn định.
- Adapter chuyển lỗi SDK thành lỗi provider nội bộ.
- API exception handler ánh xạ lỗi sang HTTP contract.
- Không swallow exception và không trả stack trace cho caller.

## Logging

Structured log tối thiểu:

- `request_id`;
- `event_id`;
- `conversation_id` nếu có;
- provider và operation;
- elapsed time và result.

Không log token, signature, API key hoặc toàn bộ dữ liệu khách.

## Provider calls

- Luôn có timeout.
- Retry chỉ cho lỗi tạm thời và operation idempotent.
- Retry dùng exponential backoff có giới hạn.
- Validate response schema trước khi dùng.

## Tests

- Domain và use case test bằng fake adapter.
- Signature test dùng fixture raw bytes.
- Webhook test gồm verification, invalid signature, duplicate và echo event.
- Không gọi provider thật trong test suite mặc định.

