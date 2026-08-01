"""Seed and verify representative legacy data around the hardening migration."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import os

import asyncpg


def _database_url() -> str:
    raw = os.environ.get("PLEXA_TEST_DATABASE_URL") or os.environ["PLEXA_DATABASE_URL"]
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def _lesson_payload() -> dict:
    return {
        "schema_version": "1.0",
        "identity": {
            "lesson_id": "shared-legacy-lesson",
            "version": "1.0.0",
            "title": "Shared legacy lesson",
            "author": "Migration test",
            "license": "MIT",
        },
        "intent": {
            "learning_objective": "Verify safe legacy migration.",
            "behavioral_focus": "Persistence",
        },
        "execution": {
            "system_prompt": "Private legacy migration prompt.",
            "initial_assistant_message": "Complete the migration check.",
            "profile": "default",
        },
        "constraints": {"input_mode": "text", "turn_limit": 4},
        "reflection": {"hooks": [], "logging_policy": "default"},
    }


async def seed() -> None:
    connection = await asyncpg.connect(_database_url())
    now = datetime.now(UTC)
    payload = _lesson_payload()
    try:
        async with connection.transaction():
            owner_id = await connection.fetchval(
                "INSERT INTO users (external_user_id, created_at) VALUES ($1, $2) RETURNING id",
                "migration-owner",
                now,
            )
            student_id = await connection.fetchval(
                "INSERT INTO users (external_user_id, created_at) VALUES ($1, $2) RETURNING id",
                "migration-student",
                now,
            )
            course_ids = []
            for course_id in ("MIGRATION-A", "MIGRATION-B"):
                course_ids.append(
                    await connection.fetchval(
                        """
                        INSERT INTO courses (
                            course_id, title, owner_user_id, discoverable,
                            created_at, lesson_timeline
                        ) VALUES ($1, $2, $3, false, $4, '[]'::jsonb)
                        RETURNING id
                        """,
                        course_id,
                        course_id,
                        owner_id,
                        now,
                    )
                )
            lesson_id = await connection.fetchval(
                """
                INSERT INTO lessons (
                    lesson_id, version, title, author, license,
                    learning_objective, behavioral_focus, schema_version,
                    payload, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
                RETURNING id
                """,
                payload["identity"]["lesson_id"],
                payload["identity"]["version"],
                payload["identity"]["title"],
                payload["identity"]["author"],
                payload["identity"]["license"],
                payload["intent"]["learning_objective"],
                payload["intent"]["behavioral_focus"],
                payload["schema_version"],
                json.dumps(payload),
                now,
            )
            for course_id in course_ids:
                await connection.execute(
                    "INSERT INTO course_lessons (course_id, lesson_id) VALUES ($1, $2)",
                    course_id,
                    lesson_id,
                )

            session_ids = []
            for index, (course_id, policy) in enumerate(
                zip(course_ids, ("default", "disabled"), strict=True),
                start=1,
            ):
                session_ids.append(
                    await connection.fetchval(
                        """
                        INSERT INTO sessions (
                            session_id, user_id, course_id, lesson_id, title,
                            created_at, updated_at, turn_count, max_turns,
                            is_active, frozen_inference_config,
                            is_completion_started, is_finalized,
                            logging_policy, reflection_hooks
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $6, 1, NULL,
                            true, '{"model":"stub"}'::jsonb,
                            false, false, $7, '[]'::jsonb
                        )
                        RETURNING id
                        """,
                        f"migration-session-{index}",
                        student_id,
                        course_id,
                        lesson_id,
                        f"Migration session {index}",
                        now,
                        policy,
                    )
                )

            await connection.execute(
                """
                INSERT INTO messages (
                    session_id, message_id, role, content, sequence_index, created_at
                ) VALUES
                    ($1, 'system-1', 'system', 'must be removed', 0, $3),
                    ($1, 'duplicate-user', 'user', 'keep first', 1, $3),
                    ($1, 'duplicate-user', 'user', 'drop duplicate', 2, $3),
                    ($2, 'system-2', 'system', 'must be removed', 0, $3),
                    ($2, 'disabled-user', 'user', 'must not persist', 1, $3)
                """,
                session_ids[0],
                session_ids[1],
                now,
            )
    finally:
        await connection.close()


async def verify() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        lessons = await connection.fetch(
            """
            SELECT c.course_id, l.id, l.owning_course_id, l.artifact_revision
            FROM lessons AS l
            JOIN courses AS c ON c.id = l.owning_course_id
            WHERE l.lesson_id = 'shared-legacy-lesson' AND l.version = '1.0.0'
            ORDER BY c.course_id
            """
        )
        assert [row["course_id"] for row in lessons] == ["MIGRATION-A", "MIGRATION-B"]
        assert all(row["artifact_revision"] == 1 for row in lessons)

        sessions = await connection.fetch(
            """
            SELECT s.session_id, c.course_id, owner.course_id AS lesson_course_id,
                   s.max_turns, s.lesson_snapshot, s.transcript_available,
                   s.transcript_unavailable_reason, s.is_active
            FROM sessions AS s
            JOIN courses AS c ON c.id = s.course_id
            JOIN lessons AS l ON l.id = s.lesson_id
            JOIN courses AS owner ON owner.id = l.owning_course_id
            WHERE s.session_id LIKE 'migration-session-%'
            ORDER BY s.session_id
            """
        )
        assert len(sessions) == 2
        assert all(row["course_id"] == row["lesson_course_id"] for row in sessions)
        assert all(row["max_turns"] == 4 for row in sessions)
        snapshots = [
            json.loads(row["lesson_snapshot"])
            if isinstance(row["lesson_snapshot"], str)
            else row["lesson_snapshot"]
            for row in sessions
        ]
        assert all(
            snapshot["execution"]["system_prompt"] == "Private legacy migration prompt."
            for snapshot in snapshots
        )
        assert sessions[1]["transcript_available"] is False
        assert sessions[1]["transcript_unavailable_reason"] == "server_restart"
        assert sessions[1]["is_active"] is False

        default_messages = await connection.fetchval(
            """
            SELECT COUNT(*) FROM messages AS m
            JOIN sessions AS s ON s.id = m.session_id
            WHERE s.session_id = 'migration-session-1'
            """
        )
        disabled_messages = await connection.fetchval(
            """
            SELECT COUNT(*) FROM messages AS m
            JOIN sessions AS s ON s.id = m.session_id
            WHERE s.session_id = 'migration-session-2'
            """
        )
        assert default_messages == 1
        assert disabled_messages == 0
        assert await connection.fetchval(
            "SELECT COUNT(*) FROM messages WHERE role = 'system'"
        ) == 0
        assert await connection.fetchval(
            "SELECT COUNT(*) FROM courses WHERE course_id = '__legacy_unscoped__'"
        ) == 0
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "verify"))
    args = parser.parse_args()
    asyncio.run(seed() if args.mode == "seed" else verify())


if __name__ == "__main__":
    main()
