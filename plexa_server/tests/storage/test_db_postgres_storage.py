import asyncio
import pytest

from plexa_server.inference.base import InferenceConfig
from plexa_server.models.encrypted_log import EncryptedLogMetadata
from plexa_server.models.log_access_audit import EncryptedLogAccessAuditEntry
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.models.message import Message
from plexa_server.models.session import Session
from plexa_server.storage.storage_interface import (
    ArtifactStorage,
    CourseStorage,
    SessionRevisionConflictError,
    SessionStorage,
    WorkspaceStateStorage,
)
from plexa_server.tests.fixtures import make_valid_lesson_payload

pytestmark = pytest.mark.postgres_only


def run(coro):
    return asyncio.run(coro)


def test_postgres_storages_implement_interfaces(
    artifact_storage,
    course_storage,
    session_storage,
    workspace_state_storage,
    storage_backend,
):
    assert isinstance(artifact_storage, ArtifactStorage)
    assert isinstance(course_storage, CourseStorage)
    assert isinstance(session_storage, SessionStorage)
    assert isinstance(workspace_state_storage, WorkspaceStateStorage)


def test_postgres_storage_health_checks(
    artifact_storage,
    course_storage,
    session_storage,
    workspace_state_storage,
    storage_backend,
):
    assert run(artifact_storage.health_check()) is True
    assert run(course_storage.health_check()) is True
    assert run(session_storage.health_check()) is True
    assert run(workspace_state_storage.health_check()) is True


def test_postgres_roundtrip_for_core_models(
    artifact_storage,
    course_storage,
    session_storage,
    valid_course_payload,
    storage_backend,
):
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    course_payload = dict(valid_course_payload)
    course_payload["lessons"] = {}
    course_payload["lesson_timeline"] = []
    course = Course.model_validate(course_payload)
    run(course_storage.save_course(course))
    run(artifact_storage.save_lesson(lesson, course_id=course.course_id))

    loaded_lesson = run(
        artifact_storage.load_lesson(
            lesson.identity.lesson_id,
            lesson.identity.version,
            course_id=course.course_id,
        )
    )
    assert loaded_lesson is not None
    assert loaded_lesson.identity.lesson_id == lesson.identity.lesson_id

    course = Course.model_validate(
        {
            **course.model_dump(),
            "lessons": {lesson.identity.lesson_id: lesson.identity.version},
            "lesson_timeline": [
                {
                    "lesson_id": lesson.identity.lesson_id,
                    "lesson_version": lesson.identity.version,
                    "starts_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
    )
    run(course_storage.save_course(course))

    loaded_course = run(course_storage.get_course(course.course_id))
    assert loaded_course is not None
    assert loaded_course.lessons[lesson.identity.lesson_id] == lesson.identity.version
    assert loaded_course.instructor_ids == [course.owner_id]
    assert loaded_course.lesson_timeline[0].lesson_id == lesson.identity.lesson_id

    session = Session(
        session_id="postgres-session-1",
        user_id="tester",
        lesson_id=lesson.identity.lesson_id,
        lesson_version=lesson.identity.version,
        course_id=course.course_id,
        messages=[
            Message(
                message_id="m1",
                session_id="postgres-session-1",
                role="system",
                content="Hello from postgres test.",
            )
        ],
        turn_count=0,
        max_turns=5,
        is_active=True,
    )
    config = InferenceConfig(model="stub-model", temperature=0.2)

    run(session_storage.save_session(session))
    run(session_storage.save_inference_config(session.session_id, config))

    loaded_session = run(session_storage.get_session(session.session_id))
    loaded_config = run(session_storage.get_inference_config(session.session_id))

    assert loaded_session is not None
    assert loaded_session.title == session.title
    assert loaded_session.course_id == course.course_id
    assert loaded_session.lesson_id == lesson.identity.lesson_id
    assert loaded_session.updated_at >= session.updated_at
    assert loaded_session.messages == []
    assert loaded_config is not None
    assert loaded_config.model == "stub-model"

    replacement_payload = lesson.model_dump(mode="json")
    replacement_payload["identity"]["version"] = "0.2.0"
    replacement = Lesson.model_validate(replacement_payload)
    run(artifact_storage.save_lesson(replacement, course_id=course.course_id))
    loaded_course.lessons[lesson.identity.lesson_id] = replacement.identity.version
    loaded_course.lesson_timeline = []
    run(course_storage.save_course(loaded_course))

    session.turn_count = 1
    stale_session = session.model_copy(deep=True)
    run(session_storage.save_session(session))
    persisted_after_rebind = run(session_storage.get_session(session.session_id))
    assert persisted_after_rebind is not None
    assert persisted_after_rebind.lesson_version == lesson.identity.version
    assert persisted_after_rebind.turn_count == 1

    stale_session.turn_count = 2
    with pytest.raises(SessionRevisionConflictError):
        run(session_storage.save_session(stale_session))


def test_postgres_encrypted_log_roundtrip(
    artifact_storage,
    storage_backend,
):
    metadata = EncryptedLogMetadata(
        instance_id="postgres-log-1",
        user_id="tester",
        course_id="CS101",
        lesson_id="lesson-1",
        lesson_version="0.1.0",
        course_owner_id="owner-1",
        authorized_instructor_ids=["owner-1", "assistant-1"],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        turn_count=0,
        is_active=True,
        log_version=1,
        artifact_sha256="abc",
        last_event_type="created",
        last_event_at="2026-01-01T00:00:00Z",
        key_id="server-managed:v1",
    )
    run(artifact_storage.save_encrypted_log("postgres-log-1", b"opaque-encrypted-data", metadata=metadata))

    loaded = run(artifact_storage.load_encrypted_log("postgres-log-1"))
    loaded_metadata = run(artifact_storage.load_encrypted_log_metadata("postgres-log-1"))
    assert loaded == b"opaque-encrypted-data"
    assert loaded_metadata is not None
    assert loaded_metadata.course_owner_id == "owner-1"
    assert loaded_metadata.authorized_instructor_ids == ["owner-1", "assistant-1"]
    listed = run(artifact_storage.list_encrypted_log_metadata(course_id="CS101", owner_id="owner-1"))
    assert len(listed) == 1
    assert listed[0].instance_id == "postgres-log-1"
    listed_for_instructor = run(
        artifact_storage.list_encrypted_log_metadata(course_id="CS101", instructor_id="assistant-1")
    )
    assert len(listed_for_instructor) == 1

    run(artifact_storage.delete_encrypted_log("postgres-log-1"))
    assert run(artifact_storage.load_encrypted_log("postgres-log-1")) is None
    assert run(artifact_storage.load_encrypted_log_metadata("postgres-log-1")) is None


def test_postgres_encrypted_log_expiry_retains_metadata(
    artifact_storage,
    storage_backend,
):
    metadata = EncryptedLogMetadata(
        instance_id="postgres-expired",
        user_id="tester",
        course_id="CS101",
        lesson_id="lesson-1",
        lesson_version="0.1.0",
        course_owner_id="owner-1",
        authorized_instructor_ids=["owner-1"],
        created_at="2026-01-01T00:00:00Z",
        artifact_sha256="abc",
        last_event_type="closed",
        key_id="server-managed:v1",
    )
    run(
        artifact_storage.save_encrypted_log(
            "postgres-expired",
            b"encrypted",
            metadata=metadata,
        )
    )

    run(artifact_storage.expire_encrypted_log_content("postgres-expired"))

    assert run(artifact_storage.load_encrypted_log("postgres-expired")) is None
    retained = run(artifact_storage.load_encrypted_log_metadata("postgres-expired"))
    assert retained is not None
    assert retained.content_available is False

    run(
        artifact_storage.save_encrypted_log(
            "postgres-expired",
            b"recreated",
            metadata=metadata,
        )
    )
    assert run(artifact_storage.load_encrypted_log("postgres-expired")) is None
    retained = run(artifact_storage.load_encrypted_log_metadata("postgres-expired"))
    assert retained is not None
    assert retained.content_available is False


def test_postgres_workspace_state_roundtrip(
    artifact_storage,
    course_storage,
    workspace_state_storage,
    valid_course_payload,
    storage_backend,
):
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    course_payload = dict(valid_course_payload)
    course_payload["lessons"] = {}
    course = Course.model_validate(course_payload)
    run(course_storage.save_course(course))
    run(artifact_storage.save_lesson(lesson, course_id=course.course_id))
    course.lessons = {lesson.identity.lesson_id: lesson.identity.version}
    run(course_storage.save_course(course))

    course_state = run(workspace_state_storage.touch_course("tester", course.course_id))
    lesson_state = run(
        workspace_state_storage.touch_lesson(
            "tester",
            course.course_id,
            lesson.identity.lesson_id,
            lesson.identity.version,
        )
    )

    listed_course_states = run(workspace_state_storage.list_course_states("tester"))
    listed_lesson_states = run(
        workspace_state_storage.list_lesson_states("tester", course_id=course.course_id)
    )

    assert course_state.course_id == course.course_id
    assert lesson_state.lesson_id == lesson.identity.lesson_id
    assert len(listed_course_states) == 1
    assert listed_course_states[0].course_id == course.course_id
    assert len(listed_lesson_states) == 1
    assert listed_lesson_states[0].lesson_version == lesson.identity.version


def test_postgres_encrypted_log_access_audit_roundtrip(
    artifact_storage,
    storage_backend,
):
    entry = EncryptedLogAccessAuditEntry(
        audit_id="audit-1",
        requester_user_id="assistant-1",
        course_id="CS101",
        session_id="session-1",
        lesson_id="lesson-1",
        lesson_version="0.1.0",
        target_user_id="tester",
        action="payload_read",
        details={"result_count": 1},
    )

    run(artifact_storage.save_encrypted_log_access_audit(entry))

    loaded = run(artifact_storage.list_encrypted_log_access_audits(course_id="CS101"))
    assert len(loaded) == 1
    assert loaded[0].audit_id == "audit-1"
    assert loaded[0].requester_user_id == "assistant-1"
    assert loaded[0].action == "payload_read"
