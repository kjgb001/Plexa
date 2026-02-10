import pytest
from pydantic import ValidationError

from plexa_server.models.lesson import Lesson


@pytest.fixture
def valid_lesson_payload():
    """
    Canonical valid lesson payload derived from the lesson author output.
    This is a golden test input.
    """
    return {
        "identity": {
            "version": "0.1.0",
            "title": "Calibration Under Uncertainty",
            "author": "Kellan",
            "course": "Test",
            "unit": "1",
            "license": "MIT",
        },
        "intent": {
            "learning_objective": "Practice evaluating uncertainty and confidence.",
            "behavioral_focus": "calibration",
            "discipline": ["philosophy", "cs"],
            "difficulty": "introductory",
        },
        "execution": {
            "system_prompt": "You are a careful tutor. If uncertain, say so.",
            "model_profile": "kl3m_safe",
            "parameters": {
                "temperature": 0.4,
                "top_p": 0.9,
                "max_tokens": 800,
            },
            "capabilities": {
                "tools_enabled": False,
                "browsing_enabled": False,
            },
        },
        "constraints": {
            "input_mode": "guided",
            "turn_limit": 8,
        },
        "reflection": {
            "reflection_prompts": [
                "Where did the model express uncertainty appropriately?",
                "Where was it overconfident?",
            ]
        },
    }


def test_valid_lesson_parses(valid_lesson_payload):
    lesson = Lesson.model_validate(valid_lesson_payload)

    assert lesson.identity.title == "Calibration Under Uncertainty"
    assert lesson.intent.behavioral_focus == "calibration"
    assert lesson.execution.model_profile == "kl3m_safe"
    assert lesson.constraints.input_mode == "guided"
    assert len(lesson.reflection.reflection_prompts) == 2


def test_missing_required_field_fails(valid_lesson_payload):
    broken_payload = valid_lesson_payload.copy()
    broken_payload["intent"] = broken_payload["intent"].copy()
    broken_payload["intent"].pop("learning_objective")

    with pytest.raises(ValidationError) as exc_info:
        Lesson.model_validate(broken_payload)

    errors = exc_info.value.errors()
    assert any(
        err["loc"] == ("intent", "learning_objective")
        for err in errors
    )
