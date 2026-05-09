"""add encrypted log metadata columns

Revision ID: 20260509_01
Revises: 20260508_01
Create Date: 2026-05-09 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260509_01"
down_revision: Union[str, None] = "20260508_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("encrypted_logs", sa.Column("user_id", sa.String(length=255), nullable=True))
    op.add_column("encrypted_logs", sa.Column("course_id", sa.String(length=255), nullable=True))
    op.add_column("encrypted_logs", sa.Column("lesson_id", sa.String(length=255), nullable=True))
    op.add_column("encrypted_logs", sa.Column("lesson_version", sa.String(length=64), nullable=True))
    op.add_column("encrypted_logs", sa.Column("course_owner_id", sa.String(length=255), nullable=True))
    op.add_column("encrypted_logs", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("encrypted_logs", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("encrypted_logs", sa.Column("turn_count", sa.Integer(), nullable=True))
    op.add_column("encrypted_logs", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.add_column("encrypted_logs", sa.Column("log_version", sa.Integer(), nullable=True))
    op.add_column("encrypted_logs", sa.Column("artifact_sha256", sa.String(length=64), nullable=True))
    op.add_column("encrypted_logs", sa.Column("last_event_type", sa.String(length=32), nullable=True))
    op.add_column("encrypted_logs", sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("encrypted_logs", sa.Column("key_scope", sa.String(length=255), nullable=True))

    op.create_index("ix_encrypted_logs_user_id", "encrypted_logs", ["user_id"], unique=False)
    op.create_index("ix_encrypted_logs_course_id", "encrypted_logs", ["course_id"], unique=False)
    op.create_index("ix_encrypted_logs_lesson_id", "encrypted_logs", ["lesson_id"], unique=False)
    op.create_index("ix_encrypted_logs_course_owner_id", "encrypted_logs", ["course_owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_encrypted_logs_course_owner_id", table_name="encrypted_logs")
    op.drop_index("ix_encrypted_logs_lesson_id", table_name="encrypted_logs")
    op.drop_index("ix_encrypted_logs_course_id", table_name="encrypted_logs")
    op.drop_index("ix_encrypted_logs_user_id", table_name="encrypted_logs")

    op.drop_column("encrypted_logs", "key_scope")
    op.drop_column("encrypted_logs", "last_event_at")
    op.drop_column("encrypted_logs", "last_event_type")
    op.drop_column("encrypted_logs", "artifact_sha256")
    op.drop_column("encrypted_logs", "log_version")
    op.drop_column("encrypted_logs", "is_active")
    op.drop_column("encrypted_logs", "turn_count")
    op.drop_column("encrypted_logs", "closed_at")
    op.drop_column("encrypted_logs", "updated_at")
    op.drop_column("encrypted_logs", "course_owner_id")
    op.drop_column("encrypted_logs", "lesson_version")
    op.drop_column("encrypted_logs", "lesson_id")
    op.drop_column("encrypted_logs", "course_id")
    op.drop_column("encrypted_logs", "user_id")
