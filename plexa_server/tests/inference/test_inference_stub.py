from plexa_server.inference.stub import StubInference
from plexa_server.inference.base import InferenceConfig
from plexa_server.models.message import Message

from datetime import datetime, UTC


def make_message(role: str, content: str):
    return Message(
        message_id="m1",
        session_id="s1",
        role=role,
        content=content,
        created_at=datetime.now(UTC),
    )


def test_stub_backend_name():
    backend = StubInference()
    assert backend.name == "stub"


def test_stub_generate_basic_response():
    backend = StubInference()

    messages = [
        make_message("system", "You are a test system."),
        make_message("user", "Hello stub."),
    ]

    config = InferenceConfig(model="stub-model")

    result = backend.generate(messages, config)

    assert "[STUB RESPONSE]" in result.content
    assert "Hello stub." in result.content
    assert result.backend == "stub"
    assert result.model == "stub-model"
    assert result.finish_reason == "stop"


def test_stub_deterministic_output():
    backend = StubInference()

    messages = [
        make_message("user", "Consistency check."),
    ]

    config = InferenceConfig(model="stub-model")

    result1 = backend.generate(messages, config)
    result2 = backend.generate(messages, config)

    assert result1.content == result2.content


def test_stub_handles_no_user_message():
    backend = StubInference()

    messages = [
        make_message("system", "System only."),
    ]

    config = InferenceConfig(model="stub-model")

    result = backend.generate(messages, config)

    assert "<no user message found>" in result.content


def test_stub_healthcheck():
    backend = StubInference()
    assert backend.healthcheck() is True
