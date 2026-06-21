"""support_hourly_and_overnight_booking

Revision ID: 3ada4cb533ab
Revises: 9aa37161f5c4
Create Date: 2026-06-20 04:45:59.941296
"""

import uuid
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '3ada4cb533ab'
down_revision: str | None = '9aa37161f5c4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Thêm cột price_per_hour vào bảng rooms
    op.add_column('rooms', sa.Column('price_per_hour', sa.Integer(), nullable=False, server_default='0'))

    # 2. Thay đổi kiểu dữ liệu cột check_in và check_out trong bảng bookings từ DATE sang TIMESTAMP WITH TIME ZONE
    # Chúng ta dùng type_coerce hoặc cast nếu có dữ liệu cũ, nhưng vì đây là database demo cục bộ, ta có thể alter column trực tiếp
    op.alter_column('bookings', 'check_in',
               existing_type=sa.Date(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False,
               postgresql_using='check_in::timestamp with time zone')
    op.alter_column('bookings', 'check_out',
               existing_type=sa.Date(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False,
               postgresql_using='check_out::timestamp with time zone')

    # 3. Làm sạch bảng rooms và seed dữ liệu Home 1, Home 2, Home 3
    # Xóa bookings trước để tránh vi phạm khóa ngoại
    op.execute("DELETE FROM bookings")
    op.execute("DELETE FROM rooms")

    rooms_table = sa.table(
        "rooms",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("price_per_night", sa.Integer),
        sa.column("price_per_hour", sa.Integer),
        sa.column("capacity", sa.Integer),
    )
    op.bulk_insert(
        rooms_table,
        [
            {
                "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
                "name": "Home 1",
                "price_per_night": 600000,
                "price_per_hour": 100000,
                "capacity": 2,
            },
            {
                "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
                "name": "Home 2",
                "price_per_night": 500000,
                "price_per_hour": 80000,
                "capacity": 2,
            },
            {
                "id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
                "name": "Home 3",
                "price_per_night": 400000,
                "price_per_hour": 60000,
                "capacity": 2,
            },
        ],
    )


def downgrade() -> None:
    # 1. Khôi phục kiểu dữ liệu cột trong bảng bookings
    op.alter_column('bookings', 'check_out',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.Date(),
               existing_nullable=False)
    op.alter_column('bookings', 'check_in',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.Date(),
               existing_nullable=False)

    # 2. Xóa cột price_per_hour khỏi bảng rooms
    op.drop_column('rooms', 'price_per_hour')
