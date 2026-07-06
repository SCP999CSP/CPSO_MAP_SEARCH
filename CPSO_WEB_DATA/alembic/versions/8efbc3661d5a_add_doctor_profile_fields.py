"""add_doctor_profile_fields

Revision ID: 8efbc3661d5a
Revises: 9e5e28019248
Create Date: 2026-05-04 18:54:30.000208

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8efbc3661d5a"
down_revision: Union[str, Sequence[str], None] = "9e5e28019248"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("doctors", sa.Column("gender", sa.String(), nullable=True))
    op.add_column("doctors", sa.Column("medical_school", sa.String(), nullable=True))
    op.add_column("doctors", sa.Column("languages_spoken", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("graduate_data", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("doctors", "graduate_data")
    op.drop_column("doctors", "languages_spoken")
    op.drop_column("doctors", "medical_school")
    op.drop_column("doctors", "gender")
