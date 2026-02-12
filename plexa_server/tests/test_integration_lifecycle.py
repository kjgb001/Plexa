import pytest

from plexa_server.storage.memory import InMemoryStorage
from plexa_server.core.sessions import SessionManager, SessionClosedError
from plexa_server.utils.lock_manager import LockManager
from plexa_server.models.lesson import Lesson
from plexa_server.inference.stub import StubInference

from plexa_server.tests.fixtures import make_valid_lesson_payload


def test_full_lesson_lifecycle_with_stub():
    storage = InMemoryStorage()
    inference = StubInference()

    manager = SessionManager(
        storage=storage,
        inference_backend=inference,
    )

    lesson = Lesson.model_validate(make_valid_lesson_payload())

    # Create session
    manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
    )

    session = storage.get_session("s1")

    # Initial system injection
    assert len(session.messages) == 1
    assert session.messages[0].role == "system"
    assert session.turn_count == 0
    assert session.is_active is True

    # First turn
    manager.submit_user_message("s1", "m1", "Hello world")

    session = storage.get_session("s1")

    assert session.turn_count == 1
    assert len(session.messages) == 3  # system + user + assistant
    assert session.messages[-2].role == "user"
    assert session.messages[-1].role == "assistant"
    assert session.is_active is True

    # Second turn (should close session)
    manager.submit_user_message("s1", "m2", "Second message")

    session = storage.get_session("s1")

    assert session.turn_count == 2
    assert session.is_active is False
    assert len(session.messages) == 5  # system + 2 user/assistant pairs

    # Further submission should fail
    with pytest.raises(SessionClosedError):
        manager.submit_user_message("s1", "m3", "Should fail")

    # Verify final transcript shape
    roles = [m.role for m in session.messages]

    assert roles == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_manual_close_and_auto_deactivation_behavior():
    storage = InMemoryStorage()
    inference = StubInference()

    manager = SessionManager(
        storage=storage,
        inference_backend=inference,
    )

    lesson = Lesson.model_validate(make_valid_lesson_payload())

    # Ensure lesson turn_limit is 2 for this test
    assert lesson.constraints.turn_limit == 2

    # Create session
    manager.create_session(
        session_id="s2",
        lesson=lesson,
        user_id="user-1",
    )

    # First turn
    manager.submit_user_message("s2", "m1", "First message")

    session = storage.get_session("s2")

    assert session.turn_count == 1
    assert session.is_active is True

    # Manually close session
    manager.close_session("s2")

    session = storage.get_session("s2")

    assert session.is_active is False

    # Attempt to send another message after manual close
    with pytest.raises(SessionClosedError):
        manager.submit_user_message("s2", "m2", "Should fail")

    # Now verify automatic deactivation on turn limit in a fresh session
    manager.create_session(
        session_id="s3",
        lesson=lesson,
        user_id="user-1",
    )

    manager.submit_user_message("s3", "m1", "First")
    manager.submit_user_message("s3", "m2", "Second")

    session = storage.get_session("s3")

    assert session.turn_count == lesson.constraints.turn_limit
    assert session.is_active is False

    # Confirm further submission fails due to automatic closure
    with pytest.raises(SessionClosedError):
        manager.submit_user_message("s3", "m3", "Exceeds limit")

