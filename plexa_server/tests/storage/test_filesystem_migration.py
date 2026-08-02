import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from plexa_server.db.bootstrap import ALEMBIC_INI_PATH
from plexa_server.db.config import DatabaseConfig
from plexa_server.inference.base import InferenceConfig
from plexa_server.models.course import Course
from plexa_server.models.encrypted_log import EncryptedLogMetadata
from plexa_server.models.lesson import Lesson
from plexa_server.models.log_access_audit import EncryptedLogAccessAuditEntry
from plexa_server.models.message import Message
from plexa_server.models.session import Session
from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
    FileSystemSessionStorage,
    FileSystemWorkspaceStateStorage,
)
from plexa_server.tests.fixtures import make_valid_lesson_payload
from plexa_server.utils.import_filesystem_to_postgres import (
    MigrationPreflightError,
    _load_source,
    import_filesystem_to_postgres,
)


def run(coro):
    return asyncio.run(coro)


async def _stamp_alembic_head(session_factory) -> None:
    config = Config(str(ALEMBIC_INI_PATH))
    heads = ScriptDirectory.from_config(config).get_heads()
    async with session_factory() as session:
        await session.execute(
            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        await session.execute(text("DELETE FROM alembic_version"))
        for head in heads:
            await session.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:head)"),
                {"head": head},
            )
        await session.commit()


async def _make_complete_source(data_dir: Path) -> None:
    artifacts = FileSystemArtifactStorage(data_dir)
    courses = FileSystemCourseStorage(data_dir)
    sessions = FileSystemSessionStorage(data_dir)
    workspace = FileSystemWorkspaceStateStorage(data_dir)
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    course = Course(
        course_id="CS101",
        title="Migration course",
        owner_id="owner-1",
        instructor_ids=["owner-1", "instructor-1"],
        enrolled_users=["student-1"],
        lessons={},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await courses.save_course(course)
    await artifacts.save_lesson(lesson, course_id=course.course_id)
    course.lessons = {lesson.identity.lesson_id: lesson.identity.version}
    await courses.save_course(course)

    config = InferenceConfig(profile="reasoning", temperature=0.4)
    first_session = Session(
        session_id="session-1",
        title="Migrated session",
        user_id="student-1",
        course_id=course.course_id,
        lesson_id=lesson.identity.lesson_id,
        lesson_version=lesson.identity.version,
        lesson_snapshot=lesson,
        frozen_inference_config=config,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        updated_at=datetime(2026, 1, 3, tzinfo=UTC),
        messages=[
            Message(
                message_id="system-1",
                session_id="session-1",
                role="system",
                content="Private prompt",
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
            Message(
                message_id="user-1",
                session_id="session-1",
                role="user",
                content="Student response",
                created_at=datetime(2026, 1, 2, 0, 1, tzinfo=UTC),
            ),
        ],
    )
    expired_session = first_session.model_copy(
        update={
            "session_id": "session-2",
            "title": "Expired log session",
            "messages": [],
            "frozen_inference_config": None,
        }
    )
    await sessions.save_session(first_session)
    await sessions.save_inference_config(first_session.session_id, config)
    await sessions.save_session(expired_session)

    blob = b"opaque encrypted bytes"
    metadata = EncryptedLogMetadata(
        instance_id=first_session.session_id,
        user_id=first_session.user_id,
        course_id=course.course_id,
        lesson_id=lesson.identity.lesson_id,
        lesson_version=lesson.identity.version,
        course_owner_id=course.owner_id,
        authorized_instructor_ids=course.instructor_ids,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        updated_at=datetime(2026, 1, 3, tzinfo=UTC),
        artifact_sha256=hashlib.sha256(blob).hexdigest(),
        last_event_type="message_commit",
        last_event_at=datetime(2026, 1, 3, tzinfo=UTC),
        key_id="legacy-key",
    )
    await artifacts.save_encrypted_log(first_session.session_id, blob, metadata)

    expired_blob = b"expired encrypted bytes"
    expired_metadata = metadata.model_copy(
        update={
            "instance_id": expired_session.session_id,
            "artifact_sha256": hashlib.sha256(expired_blob).hexdigest(),
        }
    )
    await artifacts.save_encrypted_log(expired_session.session_id, expired_blob, expired_metadata)
    await artifacts.expire_encrypted_log_content(expired_session.session_id)
    await artifacts.save_encrypted_log_access_audit(
        EncryptedLogAccessAuditEntry(
            audit_id="audit-1",
            requester_user_id="instructor-1",
            course_id=course.course_id,
            session_id=first_session.session_id,
            lesson_id=lesson.identity.lesson_id,
            lesson_version=lesson.identity.version,
            target_user_id=first_session.user_id,
            action="payload_read",
            created_at=datetime(2026, 1, 4, tzinfo=UTC),
        )
    )
    await workspace.touch_course(first_session.user_id, course.course_id)
    await workspace.touch_lesson(
        first_session.user_id,
        course.course_id,
        lesson.identity.lesson_id,
        lesson.identity.version,
    )


def test_filesystem_import_dry_run_roundtrip_and_nonempty_refusal(
    tmp_path,
    postgres_session_factory,
    monkeypatch,
):
    run(_make_complete_source(tmp_path))
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    run(_stamp_alembic_head(postgres_session_factory))
    monkeypatch.setattr(
        "plexa_server.utils.import_filesystem_to_postgres.get_named_database_config",
        lambda target: DatabaseConfig(async_url="postgresql+asyncpg://unused"),
    )
    monkeypatch.setattr(
        "plexa_server.utils.import_filesystem_to_postgres.create_session_factory",
        lambda url, echo=False: postgres_session_factory,
    )

    dry_run = run(import_filesystem_to_postgres(tmp_path, dry_run=True))
    report = run(import_filesystem_to_postgres(tmp_path))

    assert dry_run.status == "validated"
    assert all(count == 0 for count in dry_run.imported_counts.values())
    assert report.status == "imported"
    assert report.source_counts == report.imported_counts == report.verified_counts
    assert report.source_counts == {
        "courses": 1,
        "lessons": 1,
        "sessions": 2,
        "inference_configs": 1,
        "encrypted_logs": 2,
        "log_access_audits": 1,
        "course_workspace_states": 1,
        "lesson_workspace_states": 1,
    }
    assert before == {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    with pytest.raises(MigrationPreflightError, match="Target database must be empty"):
        run(import_filesystem_to_postgres(tmp_path))


def test_filesystem_import_rejects_missing_bound_lesson(tmp_path):
    courses = FileSystemCourseStorage(tmp_path)
    course = Course(
        course_id="CS101",
        title="Broken source",
        owner_id="owner-1",
        lessons={},
    )
    run(courses.save_course(course))
    course.lessons = {"missing": "1.0.0"}
    course.revision = 0
    course_path = next((tmp_path / "configs" / "courses").glob("*.json"))
    course_path.write_text(course.model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(MigrationPreflightError, match="resolved to 0 lesson documents"):
        run(_load_source(tmp_path))
