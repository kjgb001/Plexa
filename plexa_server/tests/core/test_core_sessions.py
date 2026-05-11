import asyncio
import pytest
from datetime import datetime, UTC

from plexa_server.inference.stub import StubInference
from plexa_server.inference.base import InferenceError, InferenceProfile
from plexa_server.inference.routing import InferenceRegistry, InferenceRouter
from plexa_server.core.sessions import (
    SessionManager,
    SessionClosedError,
    TurnLimitExceededError,
)
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.tests.fixtures import make_valid_lesson_payload


def run(coro):
    return asyncio.run(coro)


def test_create_session(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    session = run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    assert session.session_id == "s1"
    assert session.turn_count == 0
    assert session.is_active is True
    assert session.title.startswith("New session ")
    assert run(storage.get_session("s1")) is not None


def test_turn_increment_and_message_append(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    assistant_message = run(manager.submit_user_message(
        session_id="s1",
        message_id="m1",
        content="Hello world",
    ))

    session = run(storage.get_session("s1"))

    assert session.turn_count == 1
    assert len(session.messages) == 3
    assert session.title == "Hello world"
    assert session.messages[0].role == "system"
    assert session.messages[1].role == "user"
    assert session.messages[2].role == "assistant"
    assert assistant_message.role == "assistant"


def test_turn_limit_enforced(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))

    for i in range(session.max_turns + 1):
        try:
            run(manager.submit_user_message("s1", f"m{i}", f"Turn {i}"))
        except:
            continue

    session = run(storage.get_session("s1"))
    assert session.is_active is False
    assert session.turn_count == session.max_turns

    with pytest.raises(SessionClosedError):
        run(manager.submit_user_message("s1", "m2", "Second turn"))


def test_closed_session_rejects_messages(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    run(manager.close_session("s1"))

    with pytest.raises(SessionClosedError):
        run(manager.submit_user_message("s1", "m1", "Should fail"))


def test_atomic_rollback_on_inference_failure(setup_manager, storage_backend):
    class FailingInference(StubInference):
        async def generate(self, messages, config):
            raise InferenceError("Backend failure")

    inference = FailingInference()
    manager, storage = setup_manager(inference_backend=inference)

    lesson = Lesson.model_validate(make_valid_lesson_payload())
    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    with pytest.raises(InferenceError):
        run(manager.submit_user_message("s1", "m1", "Trigger failure"))

    session = run(storage.get_session("s1"))

    assert session.turn_count == 0
    assert len(session.messages) == 1
    assert session.is_active is True


def test_initial_system_message_injected(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))

    assert len(session.messages) == 1
    assert session.messages[0].role == "system"
    assert session.messages[0].content == lesson.execution.system_prompt


def test_initial_assistant_message_injected(setup_manager, storage_backend):
    manager, storage = setup_manager()

    payload = make_valid_lesson_payload()
    payload["execution"]["initial_assistant_message"] = "Welcome student."

    lesson = Lesson.model_validate(payload)

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))

    assert len(session.messages) == 2
    assert session.messages[0].role == "system"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].content == "Welcome student."


def test_turn_limit_derived_from_lesson(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))

    assert session.max_turns == lesson.constraints.turn_limit


def test_inference_config_frozen_and_stored(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    config = run(storage.get_inference_config("s1"))

    assert config.model == lesson.execution.profile

    if lesson.execution.parameters:
        assert config.temperature == lesson.execution.parameters.get("temperature")


def test_delete_session_removes_session_and_config(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    assert run(storage.get_session("s1")) is not None
    assert run(storage.get_inference_config("s1")) is not None

    run(manager.delete_session("s1"))

    assert run(storage.get_session("s1")) is None
    assert run(storage.get_inference_config("s1")) is None


def test_session_manager_routes_by_lesson_profile(
    session_storage,
    course_storage,
    artifact_storage,
    storage_backend,
):
    registry = InferenceRegistry()
    registry.register_backend("stub-a", StubInference())
    registry.register_backend("stub-b", StubInference())
    registry.register_profile(InferenceProfile(name="alpha", backend_id="stub-a", model="model-a"))
    registry.register_profile(InferenceProfile(name="beta", backend_id="stub-b", model="model-b"))
    router = InferenceRouter(registry)

    manager = SessionManager(storage=session_storage, inference_router=router)

    course = {
        "course_id": "CS101",
        "title": "Intro to AI",
        "description": "Routing test course",
        "owner_id": "test-owner",
        "instructor_ids": ["test-owner"],
        "enrolled_users": ["user-1"],
        "discoverable": True,
        "lessons": {},
    }
    run(course_storage.save_course(Course.model_validate(course)))

    alpha_payload = make_valid_lesson_payload()
    alpha_payload["execution"]["profile"] = "alpha"
    alpha_lesson = Lesson.model_validate(alpha_payload)
    run(artifact_storage.save_lesson(alpha_lesson))

    beta_payload = make_valid_lesson_payload()
    beta_payload["identity"]["lesson_id"] = "test-beta"
    beta_payload["execution"]["profile"] = "beta"
    beta_lesson = Lesson.model_validate(beta_payload)
    run(artifact_storage.save_lesson(beta_lesson))

    run(manager.create_session(
        session_id="alpha-session",
        lesson=alpha_lesson,
        user_id="user-1",
        course_id="CS101",
    ))
    run(manager.create_session(
        session_id="beta-session",
        lesson=beta_lesson,
        user_id="user-1",
        course_id="CS101",
    ))

    alpha_response = run(manager.submit_user_message("alpha-session", "m1", "hello alpha"))
    beta_response = run(manager.submit_user_message("beta-session", "m2", "hello beta"))

    assert "Model: model-a" in alpha_response.content
    assert "Model: model-b" in beta_response.content
