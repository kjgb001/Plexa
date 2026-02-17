import pytest
from pydantic import ValidationError
from datetime import datetime

from plexa_server.models.course import Course


def make_valid_course_payload():
    return {
        "course_id": "CS101",
        "title": "Intro to AI",
        "description": "Foundations of LLM literacy",
        "instructor": "Dr. Test",
        "term": "Fall 2026",
        "lessons": {},
    }


# Valid Course

def test_valid_course_parses():
    course = Course.model_validate(make_valid_course_payload())

    assert course.course_id == "CS101"
    assert course.title == "Intro to AI"
    assert isinstance(course.created_at, datetime)
    assert course.lessons == {}


# Missing Required Field

def test_missing_required_field_fails():
    broken = make_valid_course_payload()
    broken.pop("title")

    with pytest.raises(ValidationError) as exc_info:
        Course.model_validate(broken)

    errors = exc_info.value.errors()

    assert any(
        err["loc"] == ("title",)
        for err in errors
    )


# Lessons Default Behavior

def test_lessons_default_is_empty_dict():
    payload = make_valid_course_payload()
    payload.pop("lessons")

    course = Course.model_validate(payload)

    assert course.lessons == {}


# Type Enforcement

def test_lessons_must_be_mapping():
    broken = make_valid_course_payload()
    broken["lessons"] = ["not", "a", "dict"]

    with pytest.raises(ValidationError):
        Course.model_validate(broken)
