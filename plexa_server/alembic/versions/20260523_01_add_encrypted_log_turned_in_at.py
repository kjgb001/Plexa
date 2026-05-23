"""Add turned-in timestamp to encrypted log metadata.

Revision ID: 20260523_01
Revises: 20260522_01
Create Date: 2026-05-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260523_01"
down_revision = "20260522_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "encrypted_logs",
        sa.Column("turned_in_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("encrypted_logs", "turned_in_at")
