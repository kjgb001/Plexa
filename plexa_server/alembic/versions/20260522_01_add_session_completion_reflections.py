"""add session completion and reflection state

Revision ID: 20260522_01
Revises: 20260519_01
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260522_01"
down_revision = "20260519_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("is_completion_started", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("sessions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("is_finalized", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("sessions", sa.Column("turned_in_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("logging_policy", sa.String(length=32), nullable=False, server_default="default"),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "reflection_hooks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.alter_column("sessions", "is_completion_started", server_default=None)
    op.alter_column("sessions", "is_finalized", server_default=None)
    op.alter_column("sessions", "logging_policy", server_default=None)
    op.alter_column("sessions", "reflection_hooks", server_default=None)


def downgrade() -> None:
    op.drop_column("sessions", "reflection_hooks")
    op.drop_column("sessions", "logging_policy")
    op.drop_column("sessions", "turned_in_at")
    op.drop_column("sessions", "is_finalized")
    op.drop_column("sessions", "completed_at")
    op.drop_column("sessions", "is_completion_started")
