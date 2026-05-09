"""rename encrypted log key scope column to key id

Revision ID: 20260509_02
Revises: 20260509_01
Create Date: 2026-05-09 13:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260509_02"
down_revision: Union[str, None] = "20260509_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("encrypted_logs", "key_scope", new_column_name="key_id")


def downgrade() -> None:
    op.alter_column("encrypted_logs", "key_id", new_column_name="key_scope")
