"""initial_schema

Revision ID: 9e5e28019248
Revises:
Create Date: 2026-05-04 18:43:49.632891

已有数据库（此前用 create_tables 建表）请只执行 stamp，勿跑本迁移的 upgrade，否则会因表已存在而失败::

    uv run alembic stamp 9e5e28019248

空库或全新环境::

    uv run alembic upgrade head

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "9e5e28019248"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doctors",
        sa.Column("cpso_number", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("registration_status", sa.String(), nullable=True),
        sa.Column("registration_status_label", sa.String(), nullable=True),
        sa.Column("additional_address_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cpso_number"),
    )
    op.create_table(
        "doctor_addresses",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("cpso_number", sa.String(length=20), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("not_in_practice", sa.Boolean(), nullable=False),
        sa.Column("street1", sa.String(), nullable=True),
        sa.Column("street2", sa.String(), nullable=True),
        sa.Column("street3", sa.String(), nullable=True),
        sa.Column("street4", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("province", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("full_address", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("fax", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("geocode_status", sa.String(), nullable=True),
        sa.Column("geocoded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cpso_number"],
            ["doctors.cpso_number"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_doctor_addresses_city",
        "doctor_addresses",
        ["city"],
        unique=False,
    )
    op.create_index(
        "idx_doctor_addresses_cpso_number",
        "doctor_addresses",
        ["cpso_number"],
        unique=False,
    )
    op.create_index(
        "idx_doctor_addresses_is_primary",
        "doctor_addresses",
        ["is_primary"],
        unique=False,
    )
    op.create_index(
        "idx_doctor_addresses_postal_code",
        "doctor_addresses",
        ["postal_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_doctor_addresses_postal_code", table_name="doctor_addresses")
    op.drop_index("idx_doctor_addresses_is_primary", table_name="doctor_addresses")
    op.drop_index("idx_doctor_addresses_cpso_number", table_name="doctor_addresses")
    op.drop_index("idx_doctor_addresses_city", table_name="doctor_addresses")
    op.drop_table("doctor_addresses")
    op.drop_table("doctors")
