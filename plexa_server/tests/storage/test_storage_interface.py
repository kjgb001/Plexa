import asyncio
import pytest

from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
    FileSystemSessionStorage,
)
from plexa_server.storage.memory import InMemoryStorage
from plexa_server.storage.storage_interface import (
    ArtifactStorage,
    CourseStorage,
    SessionStorage,
)
from plexa_server.inference.base import InferenceConfig
from plexa_server.models.session import Session


def run(coro):
    return asyncio.run(coro)


def test_storage_interfaces_are_abstract():
    with pytest.raises(TypeError):
        ArtifactStorage()

    with pytest.raises(TypeError):
        CourseStorage()

    with pytest.raises(TypeError):
        SessionStorage()


def test_filesystem_storages_implement_storage_interfaces(tmp_path):
    artifact_storage = FileSystemArtifactStorage(tmp_path)
    course_storage = FileSystemCourseStorage(tmp_path)
    session_storage = FileSystemSessionStorage(tmp_path)

    assert isinstance(artifact_storage, ArtifactStorage)
    assert isinstance(course_storage, CourseStorage)
    assert isinstance(session_storage, SessionStorage)


def test_in_memory_storage_implements_session_storage():
    storage = InMemoryStorage()

    assert isinstance(storage, SessionStorage)


def test_in_memory_session_storage_lists_sessions():
    storage = InMemoryStorage()

    assert run(storage.list_sessions()) == []


def test_in_memory_session_storage_delete_clears_session_and_config():
    storage = InMemoryStorage()
    session = Session.model_validate({
        "session_id": "s1",
        "lesson_id": "intro",
        "lesson_version": "1.0",
        "user_id": "tester",
        "course_id": "CS101",
        "messages": [],
        "turn_count": 0,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
    })
    config = InferenceConfig.model_validate({
        "model": "stub",
        "temperature": 0.0,
    })

    run(storage.save_session(session))
    run(storage.save_inference_config(session.session_id, config))
    run(storage.delete_session(session.session_id))

    assert run(storage.get_session(session.session_id)) is None
    assert run(storage.get_inference_config(session.session_id)) is None
