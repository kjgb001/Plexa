import pytest
from pydantic import ValidationError

from plexa_server.models.lesson import Lesson
from plexa_server.tests.fixtures import make_valid_lesson_payload


def test_valid_lesson_parses():
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    assert lesson.identity.title == "Calibration Under Uncertainty"
    assert lesson.intent.behavioral_focus == "calibration"
    assert lesson.execution.profile == "reasoning"
    assert lesson.constraints.input_mode == "text"
    assert len(lesson.reflection.hooks) == 3
    assert lesson.reflection.hooks[0].phase == "mid"
    assert lesson.reflection.logging_policy == "default"


def test_legacy_model_profile_alias_still_parses():
    payload = make_valid_lesson_payload()
    payload["execution"] = payload["execution"].copy()
    payload["execution"]["model_profile"] = payload["execution"].pop("profile")

    lesson = Lesson.model_validate(payload)

    assert lesson.execution.profile == "reasoning"


def test_missing_required_field_fails():
    broken_payload = make_valid_lesson_payload()

    broken_payload["intent"] = broken_payload["intent"].copy()
    broken_payload["intent"].pop("learning_objective")

    with pytest.raises(ValidationError) as exc_info:
        Lesson.model_validate(broken_payload)

    errors = exc_info.value.errors()

    assert any(
        err["loc"] == ("intent", "learning_objective")
        for err in errors
    )


def test_invalid_curated_enum_fields_fail():
    broken_payload = make_valid_lesson_payload()
    broken_payload["intent"] = broken_payload["intent"].copy()
    broken_payload["reflection"] = broken_payload["reflection"].copy()
    broken_payload["intent"]["difficulty"] = "open"
    broken_payload["reflection"]["logging_policy"] = "full"

    with pytest.raises(ValidationError) as exc_info:
        Lesson.model_validate(broken_payload)

    errors = exc_info.value.errors()

    assert any(err["loc"] == ("intent", "difficulty") for err in errors)
    assert any(err["loc"] == ("reflection", "logging_policy") for err in errors)


def test_invalid_reflection_hook_shape_fails():
    broken_payload = make_valid_lesson_payload()
    broken_payload["reflection"] = broken_payload["reflection"].copy()
    broken_payload["reflection"]["hooks"] = [
        {
            "hook_id": "bad-post",
            "prompt": "Should fail",
            "phase": "post",
            "order_index": 0,
            "trigger_turn": 2,
        }
    ]

    with pytest.raises(ValidationError) as exc_info:
        Lesson.model_validate(broken_payload)

    errors = exc_info.value.errors()

    assert any(err["loc"] == ("reflection", "hooks", 0) for err in errors)
