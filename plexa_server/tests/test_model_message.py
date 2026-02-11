import pytest
from pydantic import ValidationError

from plexa_server.models.message import Message


def test_message_creation_valid():
    msg = Message(
        message_id="m1",
        role="user",
        content="Hello"
    )

    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.message_id == "m1"
    assert msg.created_at is not None


def test_message_invalid_role():
    with pytest.raises(ValidationError):
        Message(
            message_id="m2",
            role="alien",  # invalid role
            content="???"
        )


def test_message_metadata_optional():
    msg = Message(
        message_id="m3",
        role="assistant",
        content="Response",
        metadata={"confidence": 0.92}
    )

    assert msg.metadata["confidence"] == 0.92


def test_message_content_required():
    with pytest.raises(ValidationError):
        Message(
            message_id="m4",
            role="user"
            # missing content
        )
