"""add session titles

Revision ID: 20260511_01
Revises: 20260509_03
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260511_01"
down_revision = "20260509_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Untitled session"),
    )
    op.alter_column("sessions", "title", server_default=None)


def downgrade() -> None:
    op.drop_column("sessions", "title")
