import pytest
from pydantic import ValidationError

from plexa_server.models.lesson import Lesson
from plexa_server.tests.fixtures import make_valid_lesson_payload


def test_valid_lesson_parses():
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    assert lesson.identity.title == "Calibration Under Uncertainty"
    assert lesson.intent.behavioral_focus == "calibration"
    assert lesson.execution.model_profile == "kl3m_safe"
    assert lesson.constraints.input_mode == "text"
    assert len(lesson.reflection.reflection_prompts) == 2


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
