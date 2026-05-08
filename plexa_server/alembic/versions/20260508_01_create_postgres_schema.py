"""create initial postgres schema

Revision ID: 20260508_01
Revises:
Create Date: 2026-05-08 13:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260508_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_external_user_id", "users", ["external_user_id"], unique=True)

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructor", sa.String(length=255), nullable=True),
        sa.Column("term", sa.String(length=255), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("discoverable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_courses_course_id", "courses", ["course_id"], unique=True)

    op.create_table(
        "course_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("course_id", "user_id", name="uq_course_enrollment"),
    )

    op.create_table(
        "course_pending_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("course_id", "user_id", name="uq_course_pending_request"),
    )

    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lesson_id", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("course", sa.String(length=255), nullable=True),
        sa.Column("unit", sa.String(length=255), nullable=True),
        sa.Column("license", sa.String(length=255), nullable=False),
        sa.Column("lesson_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("learning_objective", sa.Text(), nullable=False),
        sa.Column("behavioral_focus", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=64), nullable=True),
        sa.Column("approximate_time", sa.String(length=255), nullable=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("lesson_id", "version", name="uq_lesson_version"),
    )
    op.create_index("ix_lessons_lesson_id", "lessons", ["lesson_id"], unique=False)

    op.create_table(
        "course_lessons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("course_id", "lesson_id", name="uq_course_lesson"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("max_turns", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("frozen_inference_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_sessions_session_id", "sessions", ["session_id"], unique=True)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "sequence_index", name="uq_session_message_index"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"], unique=False)

    op.create_table(
        "encrypted_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.String(length=255), nullable=False),
        sa.Column("encrypted_blob", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_encrypted_logs_instance_id", "encrypted_logs", ["instance_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_encrypted_logs_instance_id", table_name="encrypted_logs")
    op.drop_table("encrypted_logs")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_sessions_session_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("course_lessons")
    op.drop_index("ix_lessons_lesson_id", table_name="lessons")
    op.drop_table("lessons")
    op.drop_table("course_pending_requests")
    op.drop_table("course_enrollments")
    op.drop_index("ix_courses_course_id", table_name="courses")
    op.drop_table("courses")
    op.drop_index("ix_users_external_user_id", table_name="users")
    op.drop_table("users")
