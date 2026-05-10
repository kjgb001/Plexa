import asyncio

import pytest

from plexa_server.inference.base import (
    InferenceBackendUnavailable,
    InferenceMalformedResponse,
    InferenceRejected,
    InferenceTimeout,
    ResolvedInferenceConfig,
)
from plexa_server.inference.openai_compatible import OpenAICompatibleInference
from plexa_server.models.message import Message


def make_message(role: str, content: str) -> Message:
    return Message(
        message_id="m1",
        session_id="s1",
        role=role,
        content=content,
    )


class _FakeOpenAICompatibleInference(OpenAICompatibleInference):
    def __init__(self, *args, response=None, error=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._fake_response = response
        self._fake_error = error
        self.last_request = None

    def _request_json(self, method, path, payload, timeout_s):
        self.last_request = {
            "method": method,
            "path": path,
            "payload": payload,
            "timeout_s": timeout_s,
        }
        if self._fake_error is not None:
            raise self._fake_error
        return self._fake_response


def test_openai_compatible_backend_name():
    backend = OpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
    )
    assert backend.name == "openai-compatible"


def test_openai_compatible_uses_resolved_model():
    backend = _FakeOpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
        response={
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )

    config = ResolvedInferenceConfig(
        profile="default",
        backend_id="openai-compatible",
        backend_name="openai-compatible",
        model="llama3.1",
    )
    result = asyncio.run(backend.generate([make_message("user", "hi")], config))

    assert backend.last_request["payload"]["model"] == "llama3.1"
    assert result.model == "llama3.1"
    assert result.content == "hello"


def test_openai_compatible_maps_roles_and_uses_concrete_model():
    backend = _FakeOpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
        response={
            "choices": [{"message": {"content": "mapped"}, "finish_reason": "stop"}],
        },
    )

    config = ResolvedInferenceConfig(
        profile="fast",
        backend_id="openai-compatible",
        backend_name="openai-compatible",
        model="qwen2.5:7b",
    )
    asyncio.run(backend.generate(
        [
            make_message("system", "system"),
            make_message("instructor", "instructor guidance"),
            make_message("user", "hello"),
        ],
        config,
    ))

    assert backend.last_request["payload"]["model"] == "qwen2.5:7b"
    assert backend.last_request["payload"]["messages"][1]["role"] == "system"


def test_openai_compatible_uses_extra_without_overriding_core_fields():
    backend = _FakeOpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
        response={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
    )

    config = ResolvedInferenceConfig(
        profile="default",
        backend_id="openai-compatible",
        backend_name="openai-compatible",
        model="llama3.1",
        temperature=0.2,
        extra={"stream": False, "model": "should-not-win"},
    )
    asyncio.run(backend.generate([make_message("user", "hi")], config))

    assert backend.last_request["payload"]["stream"] is False
    assert backend.last_request["payload"]["model"] == "llama3.1"


def test_openai_compatible_parses_text_content_list():
    backend = _FakeOpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
        response={
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "part one"},
                            {"type": "text", "text": " and two"},
                        ]
                    },
                    "finish_reason": "stop",
                }
            ]
        },
    )

    result = asyncio.run(
        backend.generate(
            [make_message("user", "hi")],
            ResolvedInferenceConfig(
                profile="default",
                backend_id="openai-compatible",
                backend_name="openai-compatible",
                model="llama3.1",
            ),
        )
    )
    assert result.content == "part one and two"


def test_openai_compatible_raises_on_malformed_response():
    backend = _FakeOpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
        response={},
    )

    with pytest.raises(InferenceMalformedResponse):
        asyncio.run(
            backend.generate(
                [make_message("user", "hi")],
                ResolvedInferenceConfig(
                    profile="default",
                    backend_id="openai-compatible",
                    backend_name="openai-compatible",
                    model="llama3.1",
                ),
            )
        )


def test_openai_compatible_propagates_timeout():
    backend = _FakeOpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
        error=InferenceTimeout("timed out"),
    )

    with pytest.raises(InferenceTimeout):
        asyncio.run(
            backend.generate(
                [make_message("user", "hi")],
                ResolvedInferenceConfig(
                    profile="default",
                    backend_id="openai-compatible",
                    backend_name="openai-compatible",
                    model="llama3.1",
                ),
            )
        )


def test_openai_compatible_health_check_success():
    backend = _FakeOpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
        response={"data": []},
    )

    assert asyncio.run(backend.health_check()) is True
    assert backend.last_request["method"] == "GET"
    assert backend.last_request["path"] == "/models"


@pytest.mark.parametrize(
    "raised_error",
    [
        InferenceBackendUnavailable("down"),
        InferenceTimeout("timeout"),
        InferenceRejected("bad request"),
        InferenceMalformedResponse("bad payload"),
    ],
)
def test_openai_compatible_health_check_failure(raised_error):
    backend = _FakeOpenAICompatibleInference(
        base_url="http://localhost:11434/v1",
        error=raised_error,
    )

    assert asyncio.run(backend.health_check()) is False
