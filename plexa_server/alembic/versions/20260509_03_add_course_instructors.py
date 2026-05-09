"""add course instructors join table

Revision ID: 20260509_03
Revises: 20260509_02
Create Date: 2026-05-09 16:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260509_03"
down_revision: Union[str, None] = "20260509_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_instructors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("course_id", "user_id", name="uq_course_instructor"),
    )
    op.add_column(
        "encrypted_logs",
        sa.Column(
            "authorized_instructor_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute(
        """
        INSERT INTO course_instructors (course_id, user_id)
        SELECT courses.id, courses.owner_user_id
        FROM courses
        """
    )
    op.execute(
        """
        UPDATE encrypted_logs
        SET authorized_instructor_ids = to_jsonb(ARRAY[course_owner_id])
        WHERE course_owner_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("encrypted_logs", "authorized_instructor_ids")
    op.drop_table("course_instructors")
