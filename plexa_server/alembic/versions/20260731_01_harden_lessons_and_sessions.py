"""course-scope lessons and freeze session execution state

Revision ID: 20260731_01
Revises: 20260523_01
Create Date: 2026-07-31
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260731_01"
down_revision = "20260523_01"
branch_labels = None
depends_on = None


def _backfill_lesson_ownership() -> None:
    connection = op.get_bind()
    now = datetime.now(UTC)
    legacy_course_id: int | None = None

    def ensure_legacy_course() -> int:
        nonlocal legacy_course_id
        if legacy_course_id is not None:
            return legacy_course_id
        if connection.execute(
            sa.text("SELECT 1 FROM users WHERE external_user_id = '__legacy_system__'")
        ).scalar_one_or_none() is not None:
            raise RuntimeError(
                "Migration reserved user id '__legacy_system__' already exists; rename that user before upgrading."
            )
        if connection.execute(
            sa.text("SELECT 1 FROM courses WHERE course_id = '__legacy_unscoped__'")
        ).scalar_one_or_none() is not None:
            raise RuntimeError(
                "Migration reserved course id '__legacy_unscoped__' already exists; rename that course before upgrading."
            )

        user_id = connection.execute(
            sa.text(
                """
                INSERT INTO users (external_user_id, created_at)
                VALUES (:external_user_id, :created_at)
                RETURNING id
                """
            ),
            {"external_user_id": "__legacy_system__", "created_at": now},
        ).scalar_one()
        legacy_course_id = connection.execute(
            sa.text(
                """
                INSERT INTO courses (
                    course_id, title, description, instructor, term,
                    owner_user_id, discoverable, lesson_timeline,
                    revision, archived_at, created_at
                )
                VALUES (
                    '__legacy_unscoped__', 'Legacy unscoped lessons',
                    'Migration holding course for previously unbound lesson artifacts.',
                    NULL, NULL, :owner_user_id, false, '[]'::jsonb, 0, :created_at, :created_at
                )
                RETURNING id
                """
            ),
            {"owner_user_id": user_id, "created_at": now},
        ).scalar_one()
        return legacy_course_id

    lesson_ids = connection.execute(sa.text("SELECT id FROM lessons ORDER BY id")).scalars().all()
    for lesson_pk in lesson_ids:
        course_ids = connection.execute(
            sa.text(
                """
                SELECT DISTINCT course_id
                FROM (
                    SELECT course_id FROM course_lessons WHERE lesson_id = :lesson_id
                    UNION ALL
                    SELECT course_id FROM sessions WHERE lesson_id = :lesson_id
                    UNION ALL
                    SELECT course_id FROM user_lesson_states WHERE lesson_id = :lesson_id
                ) AS lesson_usage
                ORDER BY course_id
                """
            ),
            {"lesson_id": lesson_pk},
        ).scalars().all()
        if not course_ids:
            connection.execute(
                sa.text("UPDATE lessons SET owning_course_id = :course_id WHERE id = :lesson_id"),
                {"course_id": ensure_legacy_course(), "lesson_id": lesson_pk},
            )
            continue

        first_course_id = course_ids[0]
        connection.execute(
            sa.text("UPDATE lessons SET owning_course_id = :course_id WHERE id = :lesson_id"),
            {"course_id": first_course_id, "lesson_id": lesson_pk},
        )

        for course_id in course_ids:
            course_lesson_id = lesson_pk
            if course_id != first_course_id:
                course_lesson_id = connection.execute(
                    sa.text(
                        """
                        INSERT INTO lessons (
                            owning_course_id, lesson_id, version, title, author, course,
                            unit, license, lesson_created_at, learning_objective,
                            behavioral_focus, difficulty, approximate_time, schema_version,
                            payload, artifact_revision, created_at, updated_at
                        )
                        SELECT :course_id, lesson_id, version, title, author, course,
                               unit, license, lesson_created_at, learning_objective,
                               behavioral_focus, difficulty, approximate_time, schema_version,
                               payload, artifact_revision, created_at, updated_at
                        FROM lessons WHERE id = :lesson_id
                        RETURNING id
                        """
                    ),
                    {"course_id": course_id, "lesson_id": lesson_pk},
                ).scalar_one()
            connection.execute(
                sa.text(
                    "UPDATE course_lessons SET lesson_id = :new_id "
                    "WHERE course_id = :course_id AND lesson_id = :old_id"
                ),
                {"new_id": course_lesson_id, "course_id": course_id, "old_id": lesson_pk},
            )
            connection.execute(
                sa.text(
                    "UPDATE sessions SET lesson_id = :new_id "
                    "WHERE course_id = :course_id AND lesson_id = :old_id"
                ),
                {
                    "new_id": course_lesson_id,
                    "course_id": course_id,
                    "old_id": lesson_pk,
                },
            )
            connection.execute(
                sa.text(
                    "UPDATE user_lesson_states SET lesson_id = :new_id "
                    "WHERE course_id = :course_id AND lesson_id = :old_id"
                ),
                {
                    "new_id": course_lesson_id,
                    "course_id": course_id,
                    "old_id": lesson_pk,
                },
            )


def upgrade() -> None:
    op.add_column("courses", sa.Column("revision", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("courses", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "encrypted_logs",
        sa.Column("content_available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("encrypted_logs", "encrypted_blob", existing_type=sa.LargeBinary(), nullable=True)

    op.drop_constraint("uq_lesson_version", "lessons", type_="unique")
    op.add_column("lessons", sa.Column("owning_course_id", sa.Integer(), nullable=True))
    op.add_column("lessons", sa.Column("artifact_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "lessons",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_foreign_key(
        "fk_lessons_owning_course_id",
        "lessons",
        "courses",
        ["owning_course_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _backfill_lesson_ownership()

    op.alter_column("lessons", "owning_course_id", nullable=False)
    op.create_index("ix_lessons_owning_course_id", "lessons", ["owning_course_id"])
    op.create_unique_constraint(
        "uq_course_lesson_version",
        "lessons",
        ["owning_course_id", "lesson_id", "version"],
    )

    op.add_column("sessions", sa.Column("lesson_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column(
        "sessions", sa.Column("lesson_artifact_revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("sessions", sa.Column("lesson_content_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "sessions", sa.Column("transcript_available", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column("sessions", sa.Column("transcript_unavailable_reason", sa.String(length=64), nullable=True))
    op.add_column(
        "sessions", sa.Column("persistence_revision", sa.Integer(), nullable=False, server_default="0")
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE sessions AS s
            SET lesson_snapshot = l.payload,
                lesson_artifact_revision = l.artifact_revision,
                max_turns = COALESCE(
                    s.max_turns,
                    CASE
                        WHEN jsonb_typeof(l.payload -> 'constraints' -> 'turn_limit') = 'number'
                        THEN (l.payload -> 'constraints' ->> 'turn_limit')::integer
                    END,
                    GREATEST(s.turn_count, 1)
                )
            FROM lessons AS l
            WHERE s.lesson_id = l.id
            """
        )
    )
    connection.execute(sa.text("DELETE FROM messages WHERE role = 'system'"))
    connection.execute(
        sa.text(
            """
            DELETE FROM messages AS m
            USING sessions AS s
            WHERE m.session_id = s.id AND s.logging_policy = 'disabled'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE sessions
            SET transcript_available = false,
                transcript_unavailable_reason = 'server_restart',
                is_active = false,
                closed_at = COALESCE(closed_at, CURRENT_TIMESTAMP)
            WHERE logging_policy = 'disabled' AND turn_count > 0
            """
        )
    )
    connection.execute(
        sa.text(
            """
            WITH ranked_messages AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY session_id, message_id
                           ORDER BY sequence_index, id
                       ) AS duplicate_rank
                FROM messages
            )
            DELETE FROM messages AS m
            USING ranked_messages AS ranked
            WHERE m.id = ranked.id AND ranked.duplicate_rank > 1
            """
        )
    )
    op.create_unique_constraint("uq_session_message_id", "messages", ["session_id", "message_id"])

    for table, column in (
        ("courses", "revision"),
        ("lessons", "artifact_revision"),
        ("lessons", "updated_at"),
        ("sessions", "lesson_artifact_revision"),
        ("sessions", "transcript_available"),
        ("sessions", "persistence_revision"),
        ("encrypted_logs", "content_available"),
    ):
        op.alter_column(table, column, server_default=None)


def downgrade() -> None:
    op.execute("DELETE FROM encrypted_logs WHERE encrypted_blob IS NULL")
    op.alter_column("encrypted_logs", "encrypted_blob", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_column("encrypted_logs", "content_available")
    op.drop_constraint("uq_session_message_id", "messages", type_="unique")
    op.drop_column("sessions", "persistence_revision")
    op.drop_column("sessions", "transcript_unavailable_reason")
    op.drop_column("sessions", "transcript_available")
    op.drop_column("sessions", "lesson_content_sha256")
    op.drop_column("sessions", "lesson_artifact_revision")
    op.drop_column("sessions", "lesson_snapshot")

    op.drop_constraint("uq_course_lesson_version", "lessons", type_="unique")
    for table in ("course_lessons", "sessions", "user_lesson_states"):
        op.execute(
            sa.text(
                f"""
                WITH duplicate_map AS (
                    SELECT id,
                           MIN(id) OVER (PARTITION BY lesson_id, version) AS canonical_id
                    FROM lessons
                )
                UPDATE {table} AS target
                SET lesson_id = duplicate_map.canonical_id
                FROM duplicate_map
                WHERE target.lesson_id = duplicate_map.id
                  AND duplicate_map.id <> duplicate_map.canonical_id
                """
            )
        )
    op.execute(
        """
        DELETE FROM lessons AS duplicate
        USING lessons AS canonical
        WHERE duplicate.lesson_id = canonical.lesson_id
          AND duplicate.version = canonical.version
          AND duplicate.id > canonical.id
        """
    )
    op.drop_index("ix_lessons_owning_course_id", table_name="lessons")
    op.drop_constraint("fk_lessons_owning_course_id", "lessons", type_="foreignkey")
    op.drop_column("lessons", "updated_at")
    op.drop_column("lessons", "artifact_revision")
    op.drop_column("lessons", "owning_course_id")
    op.create_unique_constraint("uq_lesson_version", "lessons", ["lesson_id", "version"])

    op.execute("DELETE FROM courses WHERE course_id = '__legacy_unscoped__'")
    op.execute(
        """
        DELETE FROM users
        WHERE external_user_id = '__legacy_system__'
          AND NOT EXISTS (SELECT 1 FROM courses WHERE owner_user_id = users.id)
          AND NOT EXISTS (SELECT 1 FROM course_instructors WHERE user_id = users.id)
          AND NOT EXISTS (SELECT 1 FROM course_enrollments WHERE user_id = users.id)
          AND NOT EXISTS (SELECT 1 FROM sessions WHERE user_id = users.id)
        """
    )
    op.drop_column("courses", "archived_at")
    op.drop_column("courses", "revision")
