# API Contract

## Health

### `GET /health`

Response:

```json
{
  "status": "ok",
  "service": "homestay-support-api"
}
```

Health chỉ xác nhận process đang chạy. Readiness kiểm tra PostgreSQL/Redis sẽ được
thêm riêng, không làm `/health` phụ thuộc provider ngoài.

## Facebook webhook verification

### `GET /api/v1/webhooks/facebook`

Query từ Meta:

- `hub.mode`
- `hub.verify_token`
- `hub.challenge`

Khi mode và token hợp lệ, trả challenge dạng plain text với status `200`.
Token sai hoặc thiếu trả `403`.

## Facebook webhook events

### `POST /api/v1/webhooks/facebook`

Status: endpoint đã expose, xác minh signature và parse text message. Echo và event
không hỗ trợ được acknowledge nhưng không tạo message để xử lý.

Headers:

- `X-Hub-Signature-256`: bắt buộc;
- `Content-Type: application/json`.

Behavior:

- xác minh signature trên raw body trước khi parse JSON;
- acknowledge event hợp lệ bằng `200`;
- event trùng vẫn trả `200`, không lặp side effect;
- signature sai trả `401`;
- payload không hợp lệ trả `400`;
- không trả token, stack trace hoặc provider response thô.

Payload request tuân theo Meta webhook contract và không được bọc bằng API envelope.

## Internal API envelope

Endpoint nội bộ sau này dùng:

```json
{
  "success": true,
  "data": {}
}
```

Lỗi:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "request_id": "req_..."
  }
}
```

## AI structured result

Đây là application contract, không public HTTP response:

```json
{
  "intent": "booking_confirmation",
  "entities": {
    "check_in": null,
    "check_out": null,
    "guest_count": 2,
    "phone": null,
    "room_name": null
  },
  "draft_reply": "Dạ em đã chuyển thông tin cho chủ homestay xác nhận ạ.",
  "confidence": 0.91,
  "needs_human": true,
  "escalation_reason": "booking_requires_confirmation"
}
```

Backend validate schema và business rules trước khi gửi `draft_reply`.

## Stable error codes

- `INVALID_WEBHOOK_SIGNATURE`
- `INVALID_VERIFY_TOKEN`
- `INVALID_WEBHOOK_PAYLOAD`
- `INTEGRATION_NOT_CONFIGURED`
- `PROVIDER_TIMEOUT`
- `PROVIDER_UNAVAILABLE`
- `RATE_LIMITED`
- `ROOM_NOT_AVAILABLE`
- `VALIDATION_ERROR`
