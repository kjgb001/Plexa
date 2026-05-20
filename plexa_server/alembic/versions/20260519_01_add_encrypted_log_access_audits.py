"""add encrypted log access audits

Revision ID: 20260519_01
Revises: 20260512_01
Create Date: 2026-05-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260519_01"
down_revision = "20260512_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "encrypted_log_access_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("audit_id", sa.String(length=255), nullable=False),
        sa.Column("requester_user_id", sa.String(length=255), nullable=False),
        sa.Column("course_id", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("lesson_id", sa.String(length=255), nullable=True),
        sa.Column("lesson_version", sa.String(length=64), nullable=True),
        sa.Column("target_user_id", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_encrypted_log_access_audits_action"), "encrypted_log_access_audits", ["action"], unique=False)
    op.create_index(op.f("ix_encrypted_log_access_audits_audit_id"), "encrypted_log_access_audits", ["audit_id"], unique=True)
    op.create_index(op.f("ix_encrypted_log_access_audits_course_id"), "encrypted_log_access_audits", ["course_id"], unique=False)
    op.create_index(op.f("ix_encrypted_log_access_audits_created_at"), "encrypted_log_access_audits", ["created_at"], unique=False)
    op.create_index(op.f("ix_encrypted_log_access_audits_lesson_id"), "encrypted_log_access_audits", ["lesson_id"], unique=False)
    op.create_index(op.f("ix_encrypted_log_access_audits_requester_user_id"), "encrypted_log_access_audits", ["requester_user_id"], unique=False)
    op.create_index(op.f("ix_encrypted_log_access_audits_session_id"), "encrypted_log_access_audits", ["session_id"], unique=False)
    op.create_index(op.f("ix_encrypted_log_access_audits_target_user_id"), "encrypted_log_access_audits", ["target_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_encrypted_log_access_audits_target_user_id"), table_name="encrypted_log_access_audits")
    op.drop_index(op.f("ix_encrypted_log_access_audits_session_id"), table_name="encrypted_log_access_audits")
    op.drop_index(op.f("ix_encrypted_log_access_audits_requester_user_id"), table_name="encrypted_log_access_audits")
    op.drop_index(op.f("ix_encrypted_log_access_audits_lesson_id"), table_name="encrypted_log_access_audits")
    op.drop_index(op.f("ix_encrypted_log_access_audits_created_at"), table_name="encrypted_log_access_audits")
    op.drop_index(op.f("ix_encrypted_log_access_audits_course_id"), table_name="encrypted_log_access_audits")
    op.drop_index(op.f("ix_encrypted_log_access_audits_audit_id"), table_name="encrypted_log_access_audits")
    op.drop_index(op.f("ix_encrypted_log_access_audits_action"), table_name="encrypted_log_access_audits")
    op.drop_table("encrypted_log_access_audits")
