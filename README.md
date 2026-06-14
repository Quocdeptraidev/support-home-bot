# Mây Homestay Support Bot

Backend bot hỗ trợ khách của Mây Homestay qua Facebook Messenger. Hệ thống dùng AI
để hiểu tin nhắn và soạn phản hồi, dùng business rules để quyết định nghiệp vụ,
đồng thời gửi Telegram escalation cho chủ homestay khi cần can thiệp.

## Luồng MVP

```text
Facebook Messenger
  -> Meta Webhook
  -> FastAPI
  -> Redis idempotency/rate limit
  -> OpenAI classification + response draft
  -> domain rules
  -> Facebook Send API
  -> Telegram escalation khi cần
```

## Stack

- Python 3.13, FastAPI
- PostgreSQL 17, SQLAlchemy 2 async, Alembic
- Redis 8
- OpenAI Responses API
- Meta Graph API và Telegram Bot API
- Ruff, mypy, pytest
- Docker Compose

## Cấu trúc

```text
apps/api/app/
  api/                 HTTP routes và dependency providers
  application/         use cases
  domain/              models, rules và ports
  infrastructure/      PostgreSQL, Redis, Meta, OpenAI, Telegram adapters
  core/                settings, logging, errors và security
docs/                  kiến trúc, contracts, schema, decisions và ADR
```

Project hiện là backend-only. Không có web chat hoặc admin dashboard.

## Trạng thái triển khai

Foundation đã sẵn sàng:

- FastAPI và webhook verification;
- kiểm tra Facebook signature;
- PostgreSQL async và Alembic;
- Redis;
- domain ports và message-processing use case;
- OpenAI, Meta và Telegram dependencies;
- Docker, lint, typecheck và test.

Các phần nghiệp vụ kế tiếp:

- `POST` Facebook webhook và event parser;
- ORM models, migration và repositories;
- Meta Send API adapter;
- OpenAI structured-output adapter;
- Telegram notifier;
- logic nhận diện khách đã chốt và lưu booking lead.

## Chạy local

1. Tạo file môi trường:

```powershell
Copy-Item .env.example .env
```

2. Điền token cần thiết trong `.env`.

3. Khởi động:

```powershell
docker compose up --build
```

- API docs: http://localhost:8000/docs
- Healthcheck: http://localhost:8000/health
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Healthcheck chạy được khi chưa có token. Endpoint tích hợp phải kiểm tra cấu hình
và từ chối rõ ràng nếu token bắt buộc còn trống.

## Kiểm tra code

```powershell
.\scripts\check.ps1
```

## Tài liệu bắt buộc

- [Kiến trúc](docs/architecture.md)
- [Coding standards](docs/coding-standards.md)
- [API contract](docs/api-contract.md)
- [Database schema](docs/database-schema.md)
- [Product decisions](docs/product-decisions.md)
- [Provider setup](docs/provider-setup.md)
- [Architecture decisions](docs/adr/)
