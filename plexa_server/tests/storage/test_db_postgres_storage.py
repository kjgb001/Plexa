import asyncio
import pytest

from plexa_server.inference.base import InferenceConfig
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.models.message import Message
from plexa_server.models.session import Session
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage, SessionStorage
from plexa_server.tests.fixtures import make_valid_lesson_payload

pytestmark = pytest.mark.postgres_only


def run(coro):
    return asyncio.run(coro)


def test_postgres_storages_implement_interfaces(
    artifact_storage,
    course_storage,
    session_storage,
    storage_backend,
):
    assert isinstance(artifact_storage, ArtifactStorage)
    assert isinstance(course_storage, CourseStorage)
    assert isinstance(session_storage, SessionStorage)


def test_postgres_storage_health_checks(
    artifact_storage,
    course_storage,
    session_storage,
    storage_backend,
):
    assert run(artifact_storage.health_check()) is True
    assert run(course_storage.health_check()) is True
    assert run(session_storage.health_check()) is True


def test_postgres_roundtrip_for_core_models(
    artifact_storage,
    course_storage,
    session_storage,
    valid_course_payload,
    storage_backend,
):
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    run(artifact_storage.save_lesson(lesson))

    loaded_lesson = run(artifact_storage.load_lesson(lesson.identity.lesson_id, lesson.identity.version))
    assert loaded_lesson is not None
    assert loaded_lesson.identity.lesson_id == lesson.identity.lesson_id

    course_payload = dict(valid_course_payload)
    course_payload["lessons"] = {
        lesson.identity.lesson_id: lesson.identity.version,
    }
    course = Course.model_validate(course_payload)
    run(course_storage.save_course(course))

    loaded_course = run(course_storage.get_course(course.course_id))
    assert loaded_course is not None
    assert loaded_course.lessons[lesson.identity.lesson_id] == lesson.identity.version

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
    assert loaded_session.course_id == course.course_id
    assert loaded_session.lesson_id == lesson.identity.lesson_id
    assert loaded_session.messages[0].content == "Hello from postgres test."
    assert loaded_config is not None
    assert loaded_config.model == "stub-model"
