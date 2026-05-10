import pytest
from datetime import datetime
from pydantic import ValidationError

from plexa_server.inference.base import (
    InferenceConfig,
    InferenceResult,
    Usage,
    InferenceError,
    InferenceTimeout,
    InferenceBackendUnavailable,
)


def test_inference_config_is_frozen():
    config = InferenceConfig(profile="test-profile", temperature=0.5)

    with pytest.raises(ValidationError):
        config.profile = "another-profile"


def test_inference_config_accepts_legacy_model_alias():
    config = InferenceConfig(model="legacy-profile")

    assert config.profile == "legacy-profile"
    assert config.model == "legacy-profile"


def test_inference_result_creation():
    result = InferenceResult(
        content="Hello world",
        finish_reason="stop",
        backend="stub",
        model="test-model",
        usage=Usage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
    )

    assert result.content == "Hello world"
    assert result.finish_reason == "stop"
    assert result.backend == "stub"
    assert result.usage.total_tokens == 7
    assert isinstance(result.created_at, datetime)


def test_inference_error_hierarchy():
    assert issubclass(InferenceTimeout, InferenceError)
    assert issubclass(InferenceBackendUnavailable, InferenceError)
