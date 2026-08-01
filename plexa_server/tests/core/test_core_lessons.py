import pytest
from datetime import datetime

from plexa_server.core.lessons import (
    validate_lesson_runtime,
    build_initial_messages,
    freeze_inference_config,
    LessonRuntimeError,
)
from plexa_server.models.lesson import Lesson
from plexa_server.inference.base import InferenceConfig

from plexa_server.tests.fixtures import make_valid_lesson_payload


def test_validate_lesson_runtime_passes_for_valid_lesson():
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    validate_lesson_runtime(lesson)  # Should not raise


def test_validate_fails_on_empty_system_prompt():
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    lesson.execution.system_prompt = "   "

    with pytest.raises(LessonRuntimeError):
        validate_lesson_runtime(lesson)


def test_validate_fails_on_empty_inference_profile():
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    lesson.execution.profile = " "

    with pytest.raises(LessonRuntimeError):
        validate_lesson_runtime(lesson)


def test_validate_fails_on_non_positive_turn_limit():
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    lesson.constraints.turn_limit = 0

    with pytest.raises(LessonRuntimeError):
        validate_lesson_runtime(lesson)


def test_lesson_rejects_invalid_execution_parameters():
    payload = make_valid_lesson_payload()
    payload["execution"]["parameters"] = {"top_p": 2.0}

    with pytest.raises(ValueError, match="execution parameters"):
        Lesson.model_validate(payload)


def test_build_initial_messages_does_not_persist_system_prompt():
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    messages = build_initial_messages(lesson, session_id="s1")

    assert messages == []


def test_build_initial_messages_with_assistant_seed():
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    lesson.execution.initial_assistant_message = "Welcome student."

    messages = build_initial_messages(lesson, session_id="s1")

    assert len(messages) == 1
    assert messages[0].role == "assistant"
    assert messages[0].content == "Welcome student."
    assert messages[0].session_id == "s1"
    assert isinstance(messages[0].created_at, datetime)


def test_freeze_inference_config_maps_fields_correctly():
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    config = freeze_inference_config(lesson)

    assert isinstance(config, InferenceConfig)
    assert config.model == lesson.execution.profile
    assert config.temperature == 0.4
    assert config.top_p == 0.9
    assert config.timeout_s is None


def test_freeze_inference_config_handles_missing_parameters():
    lesson = Lesson.model_validate(make_valid_lesson_payload())
    lesson.execution.parameters = None

    config = freeze_inference_config(lesson)

    assert config.model == lesson.execution.profile
    assert config.temperature is None
    assert config.top_p is None
