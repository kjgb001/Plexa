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

    assert storage.list_sessions() == []
