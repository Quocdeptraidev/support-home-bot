# Provider Setup

## Facebook Messenger

Chuẩn bị trong Meta Developer App:

1. Facebook Page dùng cho demo.
2. Messenger product và Page subscription.
3. Page access token.
4. App secret.
5. Verify token do dự án tự đặt.
6. Graph API version đang được Meta App hỗ trợ.
7. HTTPS callback URL:
   `https://<public-host>/api/v1/webhooks/facebook`.

Điền:

```dotenv
FB_PAGE_ACCESS_TOKEN=
FB_APP_SECRET=
FB_VERIFY_TOKEN=
FB_API_VERSION=
```

Không lấy API version từ ví dụ cũ. Kiểm tra phiên bản hiện hành trong App Dashboard
tại thời điểm cấu hình.

## OpenAI

Tạo API key cho project riêng của demo và giới hạn quyền/ngân sách phù hợp.

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_CLASSIFICATION_MODEL=
OPENAI_RESPONSE_MODEL=
```

Nếu classification/response model để trống, ứng dụng dùng `OPENAI_MODEL`.
Code mới ưu tiên Responses API và structured output.

Tài liệu:

- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://developers.openai.com/api/docs/guides/structured-outputs

## Telegram

1. Tạo bot qua BotFather.
2. Gửi ít nhất một message vào bot hoặc group.
3. Lấy chat ID.
4. Điền:

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Telegram chỉ dùng cho escalation. Không gửi access token hoặc toàn bộ provider
payload vào nội dung thông báo.

## Local HTTPS callback

Meta cần callback HTTPS truy cập được từ internet. Ở local có thể dùng tunnel được
phê duyệt cho dự án. Không ghi URL tunnel cố định vào source; callback URL thuộc
cấu hình môi trường triển khai.

## Google Calendar

Để tích hợp và tự động điền lịch Google Calendar khi có khách đặt phòng:

1. **Tạo Google Cloud Project**: Truy cập [Google Cloud Console](https://console.cloud.google.com/) và tạo một project mới.
2. **Kích hoạt Google Calendar API**: Vào thư viện API, tìm kiếm "Google Calendar API" và kích hoạt (Enable).
3. **Tạo Service Account & Key**:
   - Truy cập **IAM & Admin** -> **Service Accounts**.
   - Chọn **Create Service Account**, điền thông tin và nhấn hoàn thành.
   - Nhấp vào Service Account vừa tạo, chọn tab **Keys** -> **Add Key** -> **Create new key** (chọn định dạng JSON).
   - Tải file JSON key về máy.
4. **Cấu hình Google Calendar (Chia sẻ lịch)**:
   - Truy cập [Google Calendar](https://calendar.google.com/).
   - Tạo một lịch mới (ví dụ: Lịch Đặt Phòng) hoặc chọn lịch hiện có của bạn.
   - Vào **Settings and sharing** của lịch đó.
   - Tại mục **Integrate calendar**, copy **Calendar ID** (thường có định dạng: `xxxx@group.calendar.google.com` hoặc email của bạn).
   - Tại mục **Share with specific people or groups**, chọn **Add people and groups**, dán địa chỉ email của Service Account vừa tạo (dạng `xxxx@xxxx.iam.gserviceaccount.com`).
   - Phân quyền (Permissions) là: **Make changes to events** (để bot có quyền tạo/sửa sự kiện).
5. **Cấu hình biến môi trường trong `.env`**:
   - `GOOGLE_CALENDAR_ID`: Dán Calendar ID lấy ở Bước 4.
   - `GOOGLE_SERVICE_ACCOUNT_INFO`: Dán toàn bộ nội dung của file JSON key lấy ở Bước 3 (chuyển đổi toàn bộ JSON thành một chuỗi duy nhất trên một dòng).


