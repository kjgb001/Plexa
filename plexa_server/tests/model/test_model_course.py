import pytest
from pydantic import ValidationError
from datetime import datetime

from plexa_server.models.course import Course


# Valid Course

def test_valid_course_parses(valid_course_payload):
    course = Course.model_validate(valid_course_payload)

    assert course.course_id == "CS101"
    assert course.title == "Intro to AI"
    assert isinstance(course.created_at, datetime)
    assert course.lessons == {}


# Missing Required Field

def test_missing_required_field_fails(valid_course_payload):
    broken = valid_course_payload
    broken.pop("title")

    with pytest.raises(ValidationError) as exc_info:
        Course.model_validate(broken)

    errors = exc_info.value.errors()

    assert any(
        err["loc"] == ("title",)
        for err in errors
    )


# Lessons Default Behavior

def test_lessons_default_is_empty_dict(valid_course_payload):
    payload = valid_course_payload
    payload.pop("lessons")

    course = Course.model_validate(payload)

    assert course.lessons == {}


# Type Enforcement

def test_lessons_must_be_mapping(valid_course_payload):
    broken = valid_course_payload
    broken["lessons"] = ["not", "a", "dict"]

    with pytest.raises(ValidationError):
        Course.model_validate(broken)
