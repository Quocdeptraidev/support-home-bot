# Quy tắc dự án Mây Homestay Support Bot

## 1. Nguồn yêu cầu

- `master-plan-bot-homestay.md` lưu ý tưởng sản phẩm ban đầu.
- `docs/product-decisions.md` là nguồn quyết định hiện hành khi hướng sản phẩm thay đổi.
- `mau.example` là tài liệu tham khảo cấu hình, không phải file môi trường để chạy.
- Khi code và tài liệu mâu thuẫn, phải cập nhật tài liệu hoặc tạo ADR trước khi mở rộng.

## 2. Phạm vi MVP hiện tại

Luồng chính:

```text
Facebook Messenger webhook
    -> FastAPI
    -> kiểm tra chữ ký, chống trùng và rate limit
    -> AI phân loại/trích xuất/soạn phản hồi
    -> business rules quyết định hành động
    -> Facebook Send API trả lời khách
    -> Telegram thông báo khi cần con người
```

- Facebook Messenger là kênh demo chính.
- Telegram là kênh cảnh báo/escalation, không thay thế phản hồi Messenger.
- PostgreSQL lưu dữ liệu bền vững; Redis phục vụ idempotency, lock, cache và rate limit.
- Project backend-only; web chat và admin dashboard không tồn tại trong source MVP.

## 3. Clean Architecture

Dependency chỉ hướng vào bên trong:

```text
api/webhooks -> application/use_cases -> domain
                       |
                       v
                domain ports
                       ^
                       |
          infrastructure adapters
```

- `domain` không phụ thuộc FastAPI, SQLAlchemy, OpenAI SDK, Redis hay Meta SDK.
- Route chỉ xác thực HTTP input, gọi use case và ánh xạ output.
- Application service điều phối use case, không chứa code framework.
- Repository chỉ truy cập dữ liệu, không chứa business rule.
- Adapter bên ngoài triển khai các protocol/port do domain hoặc application định nghĩa.
- Bot/AI không truy vấn SQLAlchemy Session trực tiếp.

Không được:

```text
Route -> Database
AI adapter -> tạo booking trực tiếp
Domain -> FastAPI/OpenAI/SQLAlchemy
```

## 4. Cấu trúc source

```text
apps/api/app/
├── api/                 # FastAPI routes, dependencies, HTTP schemas
├── application/         # use cases và orchestration
├── domain/              # entities, value objects, enums, ports, business rules
├── infrastructure/      # PostgreSQL, Redis, Meta, OpenAI, Telegram adapters
├── core/                # settings, logging, errors, security
└── main.py
```

Test phản chiếu cấu trúc source trong `apps/api/tests/`.

## 5. Dependency Injection

- Không tạo database session, HTTP client hoặc SDK client trực tiếp trong service.
- Dependency được truyền qua constructor/provider.
- Không dùng service locator hoặc singleton global để lấy database/client.
- FastAPI dependency provider là composition root, không phải nơi chứa nghiệp vụ.

## 6. Configuration và secrets

- Không hardcode token, URL, port, timezone, model hoặc API version.
- Tất cả cấu hình runtime đi qua Pydantic Settings.
- `.env.example` là danh sách biến chuẩn; `.env` không được commit.
- Không log access token, app secret, API key, webhook signature hoặc nội dung nhạy cảm.
- Placeholder không được dùng để gọi dịch vụ thật.
- `FB_API_VERSION` phải được đối chiếu với Meta App Dashboard trước khi deploy.
- Model OpenAI phải cấu hình qua env; không rải model ID trong business code.

## 7. Facebook webhook

- GET webhook dùng `FB_VERIFY_TOKEN` để xác minh subscription.
- POST webhook phải xác minh `X-Hub-Signature-256` bằng raw request body và `FB_APP_SECRET`.
- Event phải được xử lý idempotent theo Meta message/event ID.
- Webhook phải phản hồi nhanh; tác vụ chậm chuyển sang worker/queue khi cần.
- Không gửi lại message do chính Page tạo ra.
- Mọi call Graph API phải có timeout, retry có giới hạn và structured logging.

## 8. AI và bot

- AI chỉ hỗ trợ: intent classification, entity extraction, FAQ và draft reply.
- AI output phải có schema cấu trúc và được validate trước khi sử dụng.
- AI không được tự quyết định availability, giá, tạo booking, xác nhận hoặc hủy booking.
- Quyết định nghiệp vụ phải deterministic và nằm trong domain/application service.
- Khi confidence thấp, thiếu dữ liệu, vi phạm policy hoặc lỗi provider: chuyển escalation.
- Conversation history phải giới hạn và không gửi dữ liệu dư thừa tới provider.
- Ưu tiên OpenAI Responses API cho code mới.

## 9. Telegram escalation

Gửi thông báo khi:

- khách yêu cầu gặp nhân viên;
- khách có ý định đặt phòng và cần chủ nhà xác nhận;
- AI confidence thấp hoặc không tạo được phản hồi an toàn;
- Facebook/OpenAI/database gặp lỗi cần can thiệp.

Thông báo cần có correlation/request ID, PSID đã che bớt, nội dung tóm tắt và lý do escalation.

## 10. API và error contract

- Endpoint nội bộ/public đặt dưới `/api/v1`; healthcheck tại `/health`.
- Response nghiệp vụ tuân theo contract trong `docs/api-contract.md`.
- Không trả raw exception, stack trace hoặc secret cho client.
- Lỗi nghiệp vụ phải có error code ổn định.
- Webhook callback tuân theo response contract của Meta, không ép vào envelope API nội bộ.

## 11. Database và Redis

- Thay đổi schema PostgreSQL phải đi qua Alembic migration.
- Bảng nghiệp vụ có `created_at` và `updated_at`.
- Timestamp lưu UTC; ngày đặt phòng dùng timezone `Asia/Ho_Chi_Minh` ở rìa hệ thống.
- Tiền lưu integer VNĐ, không dùng float.
- Foreign key và cột truy vấn thường xuyên phải có index.
- Redis không phải nguồn dữ liệu bền vững; cache mất không được làm mất booking/conversation.

## 12. Code standards

- Python có type hints; Ruff format/lint; mypy strict.
- Không dùng `print` trong application code; dùng structured logging.
- Không hardcode magic string/number; dùng enum, constant hoặc settings.
- Function trên 50 dòng, file trên 300 dòng hoặc class trên 500 dòng phải được xem xét tách.
- Một function làm một việc; một class có một lý do để thay đổi.
- Ưu tiên code rõ ràng hơn abstraction sớm hoặc tối ưu vi mô.

## 13. Testing

Mỗi use case nghiệp vụ cần cân nhắc:

- happy path;
- validation failure;
- not found;
- duplicate/idempotency;
- boundary case;
- provider timeout/failure;
- escalation path.

Yêu cầu:

- Không gọi Facebook, OpenAI hoặc Telegram thật trong unit test.
- Signature verification, idempotency và business rules phải có unit test.
- Domain coverage mục tiêu >= 90%; application service >= 80%.
- Trước khi hoàn tất: chạy Ruff, mypy và pytest cho phần đã thay đổi.

## 14. Documentation

Thay đổi lớn phải cập nhật tài liệu liên quan:

- `docs/architecture.md`
- `docs/coding-standards.md`
- `docs/api-contract.md`
- `docs/database-schema.md`
- `docs/product-decisions.md`
- `docs/adr/`

Không hoàn tất tính năng nếu tài liệu kiến trúc hoặc contract đã lỗi thời.

## 15. Git và AI development

- Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`.
- Commit nhỏ, không trộn refactor không liên quan.
- Không sửa migration đã được sử dụng; tạo migration mới.
- Không merge code chưa đọc, chưa lint và chưa test.
- Không commit secret, `.env`, database dump hoặc dữ liệu khách thật.
