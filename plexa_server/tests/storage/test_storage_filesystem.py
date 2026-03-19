import json
from pathlib import Path

import pytest

from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemSessionStorage,
    FileSystemCourseStorage,
)
from plexa_server.models.lesson import Lesson
from plexa_server.models.session import Session
from plexa_server.models.course import Course
from plexa_server.inference.base import InferenceConfig
from plexa_server.tests.fixtures import make_valid_lesson_payload


def make_valid_session(session_id: str = "s1"):
    return Session.model_validate({
        "session_id": session_id,
        "lesson_id": "intro",
        "lesson_version": "1.0",
        "user_id": "tester",
        "course_id": "CS101",
        "messages": [],
        "turn_count": 0,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
    })


def make_valid_course(valid_course_payload):
    return Course.model_validate(valid_course_payload)


def make_valid_inference_config():
    return InferenceConfig.model_validate({
        "model": "stub",
        "temperature": 0.0,
    })


def test_artifact_storage_lesson_roundtrip(tmp_path: Path):
    storage = FileSystemArtifactStorage(tmp_path)

    lesson = Lesson.model_validate(make_valid_lesson_payload())

    storage.save_lesson(lesson)
    loaded = storage.load_lesson(
        lesson.identity.lesson_id,
        lesson.identity.version,
    )

    assert loaded is not None
    assert loaded.identity.lesson_id == lesson.identity.lesson_id
    assert loaded.identity.version == lesson.identity.version


def test_artifact_storage_log_roundtrip(tmp_path: Path):
    storage = FileSystemArtifactStorage(tmp_path)

    blob = b"encrypted-data"
    storage.save_encrypted_log("abc", blob)

    loaded = storage.load_encrypted_log("abc")

    assert loaded == blob


def test_session_storage_roundtrip(tmp_path: Path):
    storage = FileSystemSessionStorage(tmp_path)

    session = make_valid_session()

    storage.save_session(session)
    loaded = storage.get_session(session.session_id)

    assert loaded is not None
    assert loaded.session_id == session.session_id
    assert loaded.user_id == session.user_id


def test_session_storage_delete(tmp_path: Path):
    storage = FileSystemSessionStorage(tmp_path)

    session = make_valid_session()
    config = make_valid_inference_config()

    storage.save_session(session)
    storage.save_inference_config(session.session_id, config)
    storage.delete_session(session.session_id)

    assert storage.get_session(session.session_id) is None
    assert storage.get_inference_config(session.session_id) is None


def test_session_storage_inference_config_roundtrip(tmp_path: Path):
    storage = FileSystemSessionStorage(tmp_path)

    config = make_valid_inference_config()

    storage.save_inference_config("s1", config)
    loaded = storage.get_inference_config("s1")

    assert loaded is not None
    assert loaded.model == config.model


def test_session_storage_list_sessions(tmp_path: Path):
    storage = FileSystemSessionStorage(tmp_path)

    storage.save_session(make_valid_session("s1"))
    storage.save_session(make_valid_session("s2"))

    sessions = storage.list_sessions()
    session_ids = {session.session_id for session in sessions}

    assert session_ids == {"s1", "s2"}


def test_course_storage_roundtrip(tmp_path: Path, valid_course_payload):
    storage = FileSystemCourseStorage(tmp_path)

    course = make_valid_course(valid_course_payload)

    storage.save_course(course)
    loaded = storage.get_course(course.course_id)

    assert loaded is not None
    assert loaded.course_id == course.course_id
    assert loaded.title == course.title


def test_course_storage_delete(tmp_path: Path, valid_course_payload):
    storage = FileSystemCourseStorage(tmp_path)

    course = make_valid_course(valid_course_payload)

    storage.save_course(course)
    storage.delete_course(course.course_id)

    assert storage.get_course(course.course_id) is None


def test_course_storage_list(tmp_path: Path, valid_course_payload):
    storage = FileSystemCourseStorage(tmp_path)

    c1 = make_valid_course(valid_course_payload)
    c2 = Course.model_validate({
        "course_id": "CS102",
        "owner_id": "Bob",
        "title": "Advanced AI",
        "lessons": {},
    })

    storage.save_course(c1)
    storage.save_course(c2)

    courses = storage.list_courses()

    ids = {c.course_id for c in courses}

    assert "CS101" in ids
    assert "CS102" in ids
