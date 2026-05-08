import asyncio
import pytest
from plexa_server.core.sessions import SessionManager, SessionClosedError
from plexa_server.models.lesson import Lesson
from plexa_server.inference.stub import StubInference

from plexa_server.tests.fixtures import make_valid_lesson_payload


def run(coro):
    return asyncio.run(coro)


def test_full_lesson_lifecycle_with_stub(setup_manager, storage_backend):
    inference = StubInference()
    course_id = "CS101"

    manager, storage = setup_manager(inference_backend=inference)

    lesson = Lesson.model_validate(make_valid_lesson_payload())

    # Create session
    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id=course_id
    ))

    session = run(storage.get_session("s1"))

    # Initial system injection
    assert len(session.messages) == 1
    assert session.messages[0].role == "system"
    assert session.turn_count == 0
    assert session.is_active is True

    # First turn
    run(manager.submit_user_message("s1", "m1", "Hello world"))

    session = run(storage.get_session("s1"))

    assert session.turn_count == 1
    assert len(session.messages) == 3  # system + user + assistant
    assert session.messages[-2].role == "user"
    assert session.messages[-1].role == "assistant"
    assert session.is_active is True

    # Second turn (should close session)
    run(manager.submit_user_message("s1", "m2", "Second message"))

    session = run(storage.get_session("s1"))

    assert session.turn_count == 2
    assert session.is_active is False
    assert len(session.messages) == 5  # system + 2 user/assistant pairs

    # Further submission should fail
    with pytest.raises(SessionClosedError):
        run(manager.submit_user_message("s1", "m3", "Should fail"))

    # Verify final transcript shape
    roles = [m.role for m in session.messages]

    assert roles == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_manual_close_and_reload_persists_state(setup_manager, storage_backend):
    inference = StubInference()
    course_id = "CS101"

    manager, storage = setup_manager(inference_backend=inference)

    lesson = Lesson.model_validate(make_valid_lesson_payload())

    assert lesson.constraints.turn_limit == 2

    # Create session
    run(manager.create_session(
        session_id="s2",
        lesson=lesson,
        user_id="user-1",
        course_id=course_id
    ))

    # First turn
    run(manager.submit_user_message("s2", "m1", "First message"))

    session = run(storage.get_session("s2"))
    assert session.turn_count == 1
    assert session.is_active is True

    # Manually close session
    run(manager.close_session("s2"))

    session = run(storage.get_session("s2"))
    assert session.is_active is False
    assert session.turn_count == 1

    # Simulate process restart
    manager = SessionManager(
        storage=storage,
        inference_backend=inference,
    )

    # Reload session from disk
    session = run(storage.get_session("s2"))

    assert session is not None
    assert session.is_active is False
    assert session.turn_count == 1

    # Attempt to send another message after reload
    with pytest.raises(SessionClosedError):
        run(manager.submit_user_message("s2", "m2", "Should still fail"))

    # Now test automatic deactivation on the SAME session lifecycle
    # Create a new session to reach turn limit
    run(manager.create_session(
        session_id="s3",
        lesson=lesson,
        user_id="user-1",
        course_id=course_id
    ))

    run(manager.submit_user_message("s3", "m1", "First"))
    run(manager.submit_user_message("s3", "m2", "Second"))

    session = run(storage.get_session("s3"))

    assert session.turn_count == lesson.constraints.turn_limit
    assert session.is_active is False

    # Simulate restart again
    manager = SessionManager(
        storage=storage,
        inference_backend=inference,
    )

    session = run(storage.get_session("s3"))

    assert session.turn_count == lesson.constraints.turn_limit
    assert session.is_active is False

    with pytest.raises(SessionClosedError):
        run(manager.submit_user_message("s3", "m3", "Exceeds limit"))
