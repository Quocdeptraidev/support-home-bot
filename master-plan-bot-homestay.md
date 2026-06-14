# Master Plan: Bot Support Homestay 🏡
> Demo: **Mây Homestay Đà Lạt** — Hệ thống bot tự động hỗ trợ đặt phòng

---

## Mục tiêu demo

Xây dựng một homestay giả lập nhìn như thật, bao gồm:

- **Fanpage/IG demo:** Mây Homestay Đà Lạt
- **Bot inbox tự động** xử lý đặt phòng qua chat
- **Admin dashboard mini** cho chủ homestay
- **Database PostgreSQL** lưu toàn bộ dữ liệu

---

## Flow demo mẫu

```
Khách:  cuối tuần này còn phòng 2 người không?
Bot:    Dạ mình muốn check-in ngày nào ạ?

Khách:  thứ 7 đến chủ nhật
Bot:    Dạ mình đi mấy người ạ?

Khách:  2 người
Bot:    Hiện còn phòng Couple View Vườn.
        Giá: 650.000đ/đêm.
        Tổng: 650.000đ.
        Mình muốn giữ phòng không ạ?

Khách:  Có
Bot:    Dạ cho em xin SĐT để giữ phòng ạ.

Khách:  0909 xxx xxx
Bot:    Em đã ghi nhận booking. Chủ homestay sẽ xác nhận lại trong ít phút ạ.
```

---

## 3 màn hình chính

### 1. Màn chat
Giả lập khách nhắn và bot trả lời — giao diện giống Messenger, có:
- Bubble chat, avatar giả lập
- Typing indicator 1–2 giây trước khi bot trả lời (tạo cảm giác thật)
- Hiển thị thời gian gửi tin

### 2. Admin Dashboard
Chủ homestay xem danh sách booking:

| Trường | Mô tả |
|---|---|
| Khách mới | Tên / SĐT khách |
| Ngày ở | Check-in → Check-out |
| Số người | Số khách |
| Phòng | Tên phòng đã đặt |
| Tổng tiền | Số đêm × giá |
| Trạng thái | `pending` / `confirmed` / `canceled` |

### 3. Cấu hình phòng
Chủ nhập thông tin phòng:
- Tên phòng
- Giá / đêm (hoặc / người với Dorm)
- Số lượng phòng
- Sức chứa
- Mô tả

---

## Tech Stack

| Tầng | Công nghệ |
|---|---|
| Backend | Python FastAPI |
| Database | PostgreSQL |
| Frontend admin | React / Next.js |
| Bot demo | Web chat giả lập (trước) → Facebook/Instagram API (sau) |

---

## Kiến trúc hệ thống

```
[Web Chat Demo]    [Admin Dashboard]    [Facebook/IG - sau]
       │                  │                      │
       └──────────────────┴──────────────────────┘
                          │
                   [FastAPI Backend]
                  ┌───────┼────────┐
             [Bot Engine] [Booking] [Room Service]
                  └───────┼────────┘
                    [PostgreSQL]
              ┌──────┬────────┬──────────┐
           [rooms] [bookings] [conversations] [room_types]
```

---

## Database Schema

### Bảng `rooms`
```sql
CREATE TABLE rooms (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    price_per_night INTEGER NOT NULL,        -- đơn vị: VNĐ
    capacity        INTEGER NOT NULL,        -- số người tối đa
    total_units     INTEGER NOT NULL,        -- số phòng loại này
    price_type      VARCHAR(10) DEFAULT 'room', -- 'room' hoặc 'person'
    description     TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### Bảng `bookings`
```sql
CREATE TABLE bookings (
    id              SERIAL PRIMARY KEY,
    room_id         INTEGER REFERENCES rooms(id),
    check_in        DATE NOT NULL,
    check_out       DATE NOT NULL,
    num_guests      INTEGER NOT NULL,
    guest_phone     VARCHAR(20) NOT NULL,
    guest_name      VARCHAR(100),
    total_price     INTEGER NOT NULL,        -- đơn vị: VNĐ
    status          VARCHAR(20) DEFAULT 'pending', -- pending/confirmed/canceled
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### Bảng `conversations`
```sql
CREATE TABLE conversations (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(64) UNIQUE NOT NULL,
    messages        JSONB DEFAULT '[]',
    current_state   VARCHAR(50) DEFAULT 'IDLE',
    slots           JSONB DEFAULT '{}',     -- dữ liệu đang thu thập
    booking_id      INTEGER REFERENCES bookings(id),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

---

## Seed Data — 3 phòng mặc định

```sql
INSERT INTO rooms (name, price_per_night, capacity, total_units, price_type, description) VALUES
(
  'Couple View Vườn',
  650000,
  2,
  3,
  'room',
  'Phòng đôi view vườn thông, có ban công riêng. Phù hợp cho 2 người.'
),
(
  'Family Room',
  1200000,
  4,
  2,
  'room',
  'Phòng gia đình rộng rãi, 2 giường đôi, view núi Langbiang.'
),
(
  'Dorm',
  250000,
  8,
  1,
  'person',
  'Phòng tập thể 8 giường tầng, tủ khóa riêng, phù hợp hội nhóm.'
);
```

> **Lưu ý:** Phòng Dorm tính giá theo **đầu người** (`num_guests × 250.000đ`), hai phòng còn lại tính theo **đêm**.

---

## Bot Engine — State Machine

### Các trạng thái

```
IDLE
  → (nhận tin nhắn về phòng/đặt chỗ)
ASK_CHECKIN
  → (nhận ngày check-in)
ASK_CHECKOUT
  → (nhận ngày check-out)
ASK_GUESTS
  → (nhận số người)
SHOW_ROOMS
  → (hiển thị phòng phù hợp + giá)
  → (khách xác nhận)
ASK_PHONE
  → (nhận SĐT)
DONE
  → (lưu booking, thông báo hoàn tất)
```

### Slots cần thu thập

| Slot | Ví dụ đầu vào | Ghi chú |
|---|---|---|
| `check_in_date` | "thứ 7", "28/6", "cuối tuần" | Dùng `dateparser` locale `vi` |
| `check_out_date` | "chủ nhật", "hôm sau", "+1 ngày" | Mặc định = check_in + 1 |
| `num_guests` | "2 người", "đi 4 người", "chỉ mình tôi" | Extract số nguyên |
| `phone_number` | "0909123456", "090 912 3456" | Regex chuẩn hóa SĐT VN |

### Logic tính giá

```python
def calculate_price(room, check_in, check_out, num_guests):
    num_nights = (check_out - check_in).days
    if room.price_type == 'person':
        return num_guests * room.price_per_night * num_nights
    else:
        return room.price_per_night * num_nights
```

---

## API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| `POST` | `/chat` | Gửi tin nhắn, nhận phản hồi bot |
| `GET` | `/rooms` | Danh sách tất cả phòng |
| `GET` | `/rooms/available` | Check phòng còn trống theo ngày + số người |
| `POST` | `/bookings` | Tạo booking mới |
| `GET` | `/bookings` | Dashboard: lấy danh sách booking |
| `PATCH` | `/bookings/{id}/status` | Confirm / cancel booking |
| `PUT` | `/rooms/{id}` | Admin cập nhật thông tin phòng |
| `POST` | `/rooms` | Admin thêm phòng mới |

### Request/Response mẫu — `/chat`

```json
// Request
POST /chat
{
  "session_id": "abc123",
  "message": "thứ 7 đến chủ nhật"
}

// Response
{
  "reply": "Dạ mình đi mấy người ạ?",
  "state": "ASK_GUESTS",
  "slots": {
    "check_in_date": "2025-06-28",
    "check_out_date": "2025-06-29"
  }
}
```

---

## Roadmap thực hiện

### Sprint 1 — Backend nền (1–2 ngày)
- [ ] Setup FastAPI project structure
- [ ] Kết nối PostgreSQL, tạo migration
- [ ] Seed 3 phòng mặc định
- [ ] API CRUD rooms

### Sprint 2 — Bot Engine (2–3 ngày)
- [ ] Viết state machine xử lý hội thoại
- [ ] Nhận diện ngày tiếng Việt (dùng `dateparser`)
- [ ] Extract số người, SĐT
- [ ] Check availability + tính giá
- [ ] Endpoint `/chat` hoạt động end-to-end

### Sprint 3 — Web Chat UI (2 ngày)
- [ ] Giao diện chat giả lập Messenger (React)
- [ ] Bubble chat, avatar, timestamp
- [ ] Typing indicator giả
- [ ] Kết nối API `/chat`

### Sprint 4 — Admin Dashboard (2–3 ngày)
- [ ] Bảng danh sách booking + filter theo trạng thái
- [ ] Nút confirm / cancel
- [ ] Form cấu hình phòng (thêm / sửa)
- [ ] Realtime hoặc polling 30 giây để cập nhật booking mới

### Sprint 5 — Hoàn thiện demo (1–2 ngày)
- [ ] Chuẩn bị 3 kịch bản demo cố định
- [ ] Polish UI, responsive
- [ ] Test end-to-end
- [ ] Deploy (Railway / Render cho backend, Vercel cho frontend)

### Giai đoạn sau — Nối mạng xã hội (~1 tuần)
- [ ] Đăng ký Facebook Developer App
- [ ] Cấu hình Webhook Messenger
- [ ] Map session_id → PSID Facebook
- [ ] Test với tài khoản thật

---

## Lưu ý khi build

**Bot rule-based thay vì LLM cho demo**
Nhanh, ổn định, không tốn API cost khi đi chào hàng. Sau khi có khách hàng thật mới nâng cấp lên AI.

**Chuẩn bị demo script cố định**
Cần sẵn 2–3 kịch bản để không bị lỗi giữa buổi gặp khách hàng:
1. Khách book phòng thành công (flow chính)
2. Khách hỏi phòng đã hết (edge case)
3. Chủ xác nhận / hủy booking trên dashboard

**Typing indicator quan trọng cho cảm giác thật**
Delay 1.2–2 giây trước mỗi phản hồi bot, kèm hiệu ứng "..." đang nhập.

**Phân biệt giá phòng vs giá người**
Handle rõ trong Room model để tránh tính sai khi demo phòng Dorm.

---

*Tài liệu tạo cho demo: Mây Homestay Đà Lạt Bot Support System*
