import pytest
from pydantic import ValidationError

from plexa_server.models.session import Session
from plexa_server.models.message import Message


def test_session_creation_valid():
    session = Session(
        session_id="s1",
        lesson_id="lesson123",
        lesson_version="0.1.0",
        course_id="CS101",
        user_id="user42"
    )

    assert session.is_active is True
    assert session.turn_count == 0
    assert session.messages == []
    assert session.created_at is not None


def test_session_requires_user_id():
    with pytest.raises(ValidationError):
        Session(
            session_id="s2",
            lesson_id="lesson123",
            lesson_version="0.1.0",
            course_id="CS101",
            # missing user_id
        )


def test_session_can_append_message():
    session = Session(
        session_id="s3",
        lesson_id="lesson123",
        lesson_version="0.1.0",
        course_id="CS101",
        user_id="user42"
    )

    msg = Message(
        message_id="m1",
        session_id=session.session_id,
        role="user",
        content="Test"
    )

    session.messages.append(msg)
    session.turn_count += 1

    assert len(session.messages) == 1
    assert session.turn_count == 1


def test_session_close_transition():
    session = Session(
        session_id="s4",
        lesson_id="lesson123",
        lesson_version="0.1.0",
        course_id="CS101",
        user_id="user42"
    )

    session.is_active = False
    session.closed_at = session.created_at

    assert session.is_active is False
    assert session.closed_at is not None


def test_session_max_turns_optional():
    session = Session(
        session_id="s5",
        lesson_id="lesson123",
        lesson_version="0.1.0",
        course_id="CS101",
        user_id="user42",
        max_turns=5
    )

    assert session.max_turns == 5
