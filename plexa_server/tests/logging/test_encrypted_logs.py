import asyncio
import importlib.util
from datetime import UTC, datetime

import pytest

from plexa_server.core.encrypted_logs import EncryptedLogService
from plexa_server.core.sessions import SessionManager
from plexa_server.inference.stub import StubInference
from plexa_server.models.course import Course
from plexa_server.models.encrypted_log import EncryptedLogMetadata
from plexa_server.models.lesson import Lesson
from plexa_server.tests.fixtures import make_valid_lesson_payload
from plexa_server.utils.cryptography import decrypt_json, encrypt_json, generate_encryption_key


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("cryptography") is None,
    reason="Encrypted log tests require the cryptography package.",
)


def run(coro):
    return asyncio.run(coro)


def test_encrypt_json_roundtrip():
    key = generate_encryption_key()
    payload = {
        "schema_version": "1",
        "session": {"session_id": "s1"},
    }

    blob = encrypt_json(payload, key, key_id="test-key")
    loaded = decrypt_json(blob, lambda key_id: key if key_id == "test-key" else "")

    assert loaded == payload


class _StaticCourseStorage:
    def __init__(self, course_map: dict[str, dict[str, object]]):
        self._course_map = course_map

    async def get_course(self, course_id: str):
        data = self._course_map.get(course_id)
        if data is None:
            return None
        return Course.model_validate(
            {
                "course_id": course_id,
                "title": course_id,
                "owner_id": data["owner_id"],
                "instructor_ids": data.get("instructor_ids", [data["owner_id"]]),
                "discoverable": False,
                "lessons": {},
            }
        )


def test_encrypted_log_service_roundtrip(artifact_storage, storage_backend):
    key = generate_encryption_key()
    service = EncryptedLogService(
        artifact_storage=artifact_storage,
        course_storage=_StaticCourseStorage(
            {"CS101": {"owner_id": "instructor-1", "instructor_ids": ["instructor-1", "assistant-1"]}}
        ),
        encoded_key=key,
    )
    payload = {
        "schema_version": "1",
        "session": {"session_id": "s1", "user_id": "tester"},
    }
    encrypted_blob = encrypt_json(payload, key, key_id=EncryptedLogService.SERVER_MANAGED_KEY_ID)
    run(
        artifact_storage.save_encrypted_log(
            "s1",
            encrypted_blob,
            metadata=EncryptedLogMetadata(
                instance_id="s1",
                user_id="tester",
                course_id="CS101",
                lesson_id="lesson-1",
                lesson_version="0.1.0",
                course_owner_id="instructor-1",
                authorized_instructor_ids=["instructor-1", "assistant-1"],
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, tzinfo=UTC),
                turn_count=0,
                is_active=True,
                log_version=1,
                artifact_sha256="abc",
                last_event_type="created",
                last_event_at=datetime(2026, 1, 1, tzinfo=UTC),
                key_id=EncryptedLogService.SERVER_MANAGED_KEY_ID,
            ),
        )
    )

    loaded = run(service.load_session_log_for_requester("s1", "instructor-1"))
    assert loaded == payload
    loaded_for_assistant = run(service.load_session_log_for_requester("s1", "assistant-1"))
    assert loaded_for_assistant == payload
    assert run(service.load_session_log_for_requester("s1", "student-1")) is None

    metadata = run(service.list_session_log_metadata_for_requester("instructor-1", course_id="CS101"))
    assert len(metadata) == 1
    assert metadata[0].instance_id == "s1"
    assert metadata[0].key_id == EncryptedLogService.SERVER_MANAGED_KEY_ID
    assert run(service.list_session_log_metadata_for_requester("student-1", course_id="CS101")) == []

    run(service.delete_session_log("s1"))
    assert run(artifact_storage.load_encrypted_log("s1")) is None


def test_encrypted_log_access_uses_current_course_ownership(artifact_storage, storage_backend):
    key = generate_encryption_key()
    service = EncryptedLogService(
        artifact_storage=artifact_storage,
        course_storage=_StaticCourseStorage(
            {"CS101": {"owner_id": "new-owner", "instructor_ids": ["new-owner", "assistant-2"]}}
        ),
        encoded_key=key,
    )
    payload = {
        "schema_version": "1",
        "session": {"session_id": "reassigned-s1", "user_id": "tester"},
    }
    encrypted_blob = encrypt_json(payload, key, key_id=EncryptedLogService.SERVER_MANAGED_KEY_ID)
    run(
        artifact_storage.save_encrypted_log(
            "reassigned-s1",
            encrypted_blob,
            metadata=EncryptedLogMetadata(
                instance_id="reassigned-s1",
                user_id="tester",
                course_id="CS101",
                lesson_id="lesson-1",
                lesson_version="0.1.0",
                course_owner_id="old-owner",
                authorized_instructor_ids=["old-owner"],
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, tzinfo=UTC),
                turn_count=0,
                is_active=True,
                log_version=1,
                artifact_sha256="abc",
                last_event_type="created",
                last_event_at=datetime(2026, 1, 1, tzinfo=UTC),
                key_id=EncryptedLogService.SERVER_MANAGED_KEY_ID,
            ),
        )
    )

    assert run(service.load_session_log_for_requester("reassigned-s1", "old-owner")) is None
    loaded = run(service.load_session_log_for_requester("reassigned-s1", "new-owner"))
    assert loaded == payload
    visible = run(service.list_session_log_metadata_for_requester("new-owner", course_id="CS101"))
    assert len(visible) == 1
    assistant_visible = run(service.list_session_log_metadata_for_requester("assistant-2", course_id="CS101"))
    assert len(assistant_visible) == 1


def test_session_manager_persists_and_deletes_encrypted_logs(
    artifact_storage,
    course_storage,
    session_storage,
    storage_backend,
):
    key = generate_encryption_key()
    service = EncryptedLogService(
        artifact_storage=artifact_storage,
        course_storage=course_storage,
        encoded_key=key,
    )
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    course = Course.model_validate(
        {
            "course_id": "CS101",
            "title": "Intro to AI",
            "description": "Encrypted log test course",
            "owner_id": "test-owner",
            "instructor_ids": ["test-owner", "assistant-owner"],
            "enrolled_users": ["user-1"],
            "discoverable": True,
            "lessons": {
                lesson.identity.lesson_id: lesson.identity.version,
            },
        }
    )

    run(artifact_storage.save_lesson(lesson))
    run(course_storage.save_course(course))

    manager = SessionManager(
        storage=session_storage,
        inference_backend=StubInference(),
        encrypted_log_service=service,
    )

    created = run(
        manager.create_session(
            session_id="session-log-1",
            lesson=lesson,
            user_id="user-1",
            course_id="CS101",
        )
    )

    created_log = run(service.load_session_log_for_requester("session-log-1", "test-owner"))
    assert created_log is not None
    assert created_log["session"]["session_id"] == created.session_id
    assert created_log["session"]["messages"][0]["role"] == "system"
    assert created_log["inference_config"]["profile"] == lesson.execution.profile

    created_metadata = run(artifact_storage.load_encrypted_log_metadata("session-log-1"))
    assert created_metadata is not None
    assert created_metadata.course_owner_id == "test-owner"
    assert created_metadata.authorized_instructor_ids == ["test-owner", "assistant-owner"]
    assert created_metadata.course_id == "CS101"
    assert created_metadata.lesson_id == lesson.identity.lesson_id
    assert created_metadata.last_event_type == "created"

    run(manager.submit_user_message("session-log-1", "m1", "Hello there"))
    updated_log = run(service.load_session_log_for_requester("session-log-1", "test-owner"))
    assert updated_log is not None
    assert updated_log["session"]["turn_count"] == 1
    assert len(updated_log["session"]["messages"]) == 3
    assert updated_log["session"]["messages"][-1]["role"] == "assistant"
    updated_metadata = run(artifact_storage.load_encrypted_log_metadata("session-log-1"))
    assert updated_metadata is not None
    assert updated_metadata.last_event_type == "message_commit"
    assert updated_metadata.turn_count == 1
    assert updated_metadata.course_owner_id == "test-owner"
    assert updated_metadata.authorized_instructor_ids == ["test-owner", "assistant-owner"]
    assert updated_metadata.key_id == EncryptedLogService.SERVER_MANAGED_KEY_ID

    run(manager.close_session("session-log-1"))
    closed_log = run(service.load_session_log_for_requester("session-log-1", "test-owner"))
    assert closed_log is not None
    assert closed_log["session"]["is_active"] is False
    closed_metadata = run(artifact_storage.load_encrypted_log_metadata("session-log-1"))
    assert closed_metadata is not None
    assert closed_metadata.last_event_type == "closed"
    assert closed_metadata.is_active is False
    assert closed_metadata.closed_at is not None

    run(manager.delete_session("session-log-1"))
    assert run(artifact_storage.load_encrypted_log("session-log-1")) is None
    assert run(artifact_storage.load_encrypted_log_metadata("session-log-1")) is None
